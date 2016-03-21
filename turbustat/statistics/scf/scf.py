# Licensed under an MIT open source license - see LICENSE


import numpy as np
import cPickle as pickle
from copy import deepcopy
from astropy import units as u

from ..psds import pspec
from ..base_statistic import BaseStatisticMixIn
from ...io import common_types, threed_types


class SCF(BaseStatisticMixIn):
    '''
    Computes the Spectral Correlation Function of a data cube
    (Rosolowsky et al, 1999).

    Parameters
    ----------
    cube : %(dtypes)s
        Data cube.
    header : FITS header, optional
        Header for the cube.
    size : int, optional
        Maximum size roll over which SCF will be calculated.
    '''

    __doc__ %= {"dtypes": " or ".join(common_types + threed_types)}

    def __init__(self, cube, header=None, size=11):
        super(SCF, self).__init__()

        # Set data and header
        self.input_data_header(cube, header)

        if size % 2 == 0:
            Warning("Size must be odd. Reducing size to next lowest odd"
                    " number.")
            self.size = size - 1
        else:
            self.size = size

        self._scf_surface = None
        self._scf_spectrum_stddev = None

    @property
    def scf_surface(self):
        return self._scf_surface

    @property
    def scf_spectrum(self):
        return self._scf_spectrum

    @property
    def scf_spectrum_stddev(self):
        if not self._stddev_flag:
            Warning("scf_spectrum_stddev is only calculated when return_stddev"
                    " is enabled.")
        return self._scf_spectrum_stddev

    @property
    def lags(self):
        return self._lags

    def compute_surface(self):
        '''
        Compute the SCF up to the given size.
        '''

        self._scf_surface = np.zeros((self.size, self.size))

        dx = np.arange(self.size) - self.size / 2
        dy = np.arange(self.size) - self.size / 2

        for i in dx:
            for j in dy:
                tmp = np.roll(self.data, i, axis=1)
                tmp = np.roll(tmp, j, axis=2)
                values = np.nansum(((self.data - tmp) ** 2), axis=0) / \
                    (np.nansum(self.data ** 2, axis=0) +
                     np.nansum(tmp ** 2, axis=0))

                scf_value = 1. - \
                    np.sqrt(np.nansum(values) / np.sum(np.isfinite(values)))
                self._scf_surface[i+self.size/2, j+self.size/2] = scf_value

    def compute_spectrum(self, logspacing=False, return_stddev=False,
                         **kwargs):
        '''
        Compute the 1D spectrum as a function of lag. Can optionally
        use log-spaced bins. kwargs are passed into the pspec function,
        which provides many options. The default settings are applicable in
        nearly all use cases.

        Parameters
        ----------
        logspacing : bool, optional
            Return logarithmically spaced bins for the lags.
        return_stddev : bool, optional
            Return the standard deviation in the 1D bins.
        kwargs : passed to pspec
        '''

        # If scf_surface hasn't been computed, do it
        if self.scf_surface is None:
            self.compute_surface()

        if return_stddev:
            self._lags, self._scf_spectrum, self._scf_spectrum_stddev = \
                pspec(self.scf_surface, logspacing=logspacing,
                      return_stddev=return_stddev, return_freqs=False,
                      **kwargs)
            self._stddev_flag = True
        else:
            self._lags, self._scf_spectrum = \
                pspec(self.scf_surface, logspacing=logspacing,
                      return_freqs=False, **kwargs)
            self._stddev_flag = False

        self._lags = self._lags * u.pix

    def save_results(self, output_name=None, keep_data=False):
        '''
        Save the results of the dendrogram statistics to avoid re-computing.
        The pickled file will not include the data cube by default.

        Parameters
        ----------
        output_name : str, optional
            Name of the outputted pickle file.
        keep_data : bool, optional
            Save the data cube in the pickle file when enabled.
        '''

        if output_name is None:
            output_name = "scf_output.pkl"

        if output_name[-4:] != ".pkl":
            output_name += ".pkl"

        self_copy = deepcopy(self)

        # Don't keep the whole cube unless keep_data enabled.
        if not keep_data:
            self_copy.cube = None

        with open(output_name, 'wb') as output:
                pickle.dump(self_copy, output, -1)

    @staticmethod
    def load_results(pickle_file):
        '''
        Load in a saved pickle file.

        Parameters
        ----------
        pickle_file : str
            Name of filename to load in.

        Returns
        -------
        self : SCF instance
            SCF instance with saved results.

        Examples
        --------
        Load saved results.
        >>> scf = SCF.load_results("scf_saved.pkl") # doctest: +SKIP

        '''

        with open(pickle_file, 'rb') as input:
                self = pickle.load(input)

        return self

    def run(self, logspacing=False, return_stddev=False, verbose=False,
            save_results=False, output_name=None, ang_units=False,
            unit=u.deg):
        '''
        Computes the SCF. Necessary to maintain package standards.

        Parameters
        ----------
        logspacing : bool, optional
            Return logarithmically spaced bins for the lags.
        return_stddev : bool, optional
            Return the standard deviation in the 1D bins.
        verbose : bool, optional
            Enables plotting.
        save_results : bool, optional
            Pickle the results.
        output_name : str, optional
            Name of the outputted pickle file.
        ang_units : bool, optional
            Convert frequencies to angular units using the given header.
        unit : u.Unit, optional
            Choose the angular unit to convert to when ang_units is enabled.
        '''

        self.compute_surface()
        self.compute_spectrum(logspacing=logspacing,
                              return_stddev=return_stddev)

        if save_results:
            self.save_results(output_name=output_name)

        if verbose:
            import matplotlib.pyplot as p

            p.subplot(1, 2, 1)
            p.imshow(self.scf_surface, origin="lower", interpolation="nearest")
            cb = p.colorbar()
            cb.set_label("SCF Value")

            p.subplot(2, 2, 2)
            p.hist(self.scf_surface.ravel())
            p.xlabel("SCF Value")

            ax = p.subplot(2, 2, 4)
            if ang_units:
                lags = \
                    self.lags.to(unit, equivalencies=self.angular_equiv).value
            else:
                lags = self.lags.value

            if self._stddev_flag:
                ax.errorbar(lags, self.scf_spectrum,
                            yerr=self.scf_spectrum_stddev,
                            fmt='D-', color='k', markersize=5)
                ax.set_xscale("log", nonposy='clip')
            else:
                p.semilogx(self.lags, self.scf_spectrum, 'kD-',
                           markersize=5)

            if ang_units:
                ax.set_xlabel("Lag ("+unit.to_string()+")")
            else:
                ax.set_xlabel("Lag (pixels)")

            p.tight_layout()
            p.show()


class SCF_Distance(object):

    '''
    Calculates the distance between two data cubes based on their SCF surfaces.
    The distance is the L2 norm between the surfaces. We weight the surface by
    1/r^2 where r is the distance from the centre.

    Parameters
    ----------
    cube1 : %(dtypes)s
        Data cube.
    cube2 : %(dtypes)s
        Data cube.
    size : int, optional
        Maximum size roll over which SCF will be calculated.
    fiducial_model : SCF
        Computed SCF object. Use to avoid recomputing.
    weighted : bool, optional
        Sets whether to apply the 1/r^2 weighting to the distance.
    '''

    __doc__ %= {"dtypes": " or ".join(common_types + threed_types)}

    def __init__(self, cube1, cube2, size=21, fiducial_model=None,
                 weighted=True):
        super(SCF_Distance, self).__init__()
        self.size = size
        self.weighted = weighted

        if fiducial_model is not None:
            self.scf1 = fiducial_model
        else:
            self.scf1 = SCF(cube1, size=self.size)
            self.scf1.run(return_stddev=True)

        self.scf2 = SCF(cube2, size=self.size)
        self.scf2.run(return_stddev=True)

    def distance_metric(self, verbose=False, label1=None, label2=None,
                        ang_units=False, unit=u.deg):
        '''
        Compute the distance between the surfaces.

        Parameters
        ----------
        verbose : bool, optional
            Enables plotting.
        label1 : str, optional
            Object or region name for cube1
        label2 : str, optional
            Object or region name for cube2
        ang_units : bool, optional
            Convert frequencies to angular units using the given header.
        unit : u.Unit, optional
            Choose the angular unit to convert to when ang_units is enabled.
        '''

        dx = np.arange(self.size) - self.size / 2
        dy = np.arange(self.size) - self.size / 2

        a, b = np.meshgrid(dx, dy)
        if self.weighted:
            # Centre pixel set to 1
            a[np.where(a == 0)] = 1.
            b[np.where(b == 0)] = 1.
            dist_weight = 1 / np.sqrt(a ** 2 + b ** 2)
        else:
            dist_weight = np.ones((self.size, self.size))

        difference = (self.scf1.scf_surface - self.scf2.scf_surface) ** 2. * \
            dist_weight
        self.distance = np.sqrt(np.sum(difference) / np.sum(dist_weight))

        if verbose:
            import matplotlib.pyplot as p

            # print "Distance: %s" % (self.distance)

            p.subplot(2, 2, 1)
            p.imshow(
                self.scf1.scf_surface, origin="lower", interpolation="nearest")
            p.title(label1)
            p.colorbar()
            p.subplot(2, 2, 2)
            p.imshow(
                self.scf2.scf_surface, origin="lower", interpolation="nearest",
                label=label2)
            p.title(label2)
            p.colorbar()
            p.subplot(2, 2, 3)
            p.imshow(difference, origin="lower", interpolation="nearest")
            p.title("Weighted Difference")
            p.colorbar()
            ax = p.subplot(2, 2, 4)
            if ang_units:
                lags1 = \
                    self.scf1.lags.to(unit,
                                      equivalencies=self.scf1.angular_equiv).value
                lags2 = \
                    self.scf2.lags.to(unit,
                                      equivalencies=self.scf2.angular_equiv).value
            else:
                lags1 = self.scf1.lags.value
                lags2 = self.scf2.lags.value

            ax.errorbar(lags1, self.scf1.scf_spectrum,
                        yerr=self.scf1.scf_spectrum_stddev,
                        fmt='D-', color='b', markersize=5, label=label1)
            ax.errorbar(lags2, self.scf2.scf_spectrum,
                        yerr=self.scf2.scf_spectrum_stddev,
                        fmt='o-', color='g', markersize=5, label=label2)
            ax.set_xscale("log", nonposy='clip')
            ax.legend(loc='upper right')
            p.tight_layout()
            p.show()

        return self
