
'''
Routines for transforming data cubes to 2D representations
'''

import numpy as np


def intensity_data(cube, p=0.1, noise_lim=0.1):
    '''
    Clips off channels below the given noise limit and keep the
    upper percentile specified.

    Parameters
    ----------
    cube : numpy.ndarray
        Data cube.
    p : float, optional
        Sets the fraction of data to keep in each channel.
    noise_lim : float, optional
        The noise limit used to reject channels in the cube.

    Returns
    -------

    intensity_vecs : numpy.ndarray
        2D dataset of size (# channels, p * cube.shape[1] * cube.shape[2]).
    '''
    vec_length = int(round(p * cube.shape[1] * cube.shape[2]))
    intensity_vecs = np.empty((cube.shape[0], vec_length))

    delete_channels = []

    for dv in range(cube.shape[0]):
        vec_vec = cube[dv, :, :]
        # Remove nans from the slice
        vel_vec = vec_vec[np.isfinite(vec_vec)]
        # Apply noise limit
        vel_vec = vel_vec[vel_vec > noise_lim]
        vel_vec.sort()
        if len(vel_vec) < vec_length:
            diff = vec_length - len(vel_vec)
            vel_vec = np.append(vel_vec, [0.0] * diff)
        else:
            vel_vec = vel_vec[:vec_length]

        # Return the normalized, shortened vector
        maxval = np.max(vel_vec)
        if maxval != 0.0:
            intensity_vecs[dv, :] = vel_vec / maxval
        else:
            delete_channels.append(dv)
    # Remove channels
    intensity_vecs = np.delete(intensity_vecs, delete_channels, axis=0)

    return intensity_vecs


def _format_data(cube, data_format='intensity', num_spec=1000,
                 noise_lim=0.0, p=0.1):
    '''
    Rearrange data into a 2D object using the given format.
    '''

    if data_format is "spectra":
        if num_spec is None:
            raise ValueError('Must specify num_spec for data format',
                             'spectra.')

        # Find the brightest spectra in the cube
        mom0 = np.nansum(cube)

        bright_spectra = \
            np.argpartition(mom0.ravel(), -num_spec)[-num_spec:]

        x = np.empty((num_spec,))
        y = np.empty((num_spec,))

        for i in range(num_spec):
            x[i] = bright_spectra[i] / cube.shape[1]
            y[i] = bright_spectra[i] % cube.shape[2]

        data_matrix = cube[:, x, y]

    elif data_format is "intensity":
        data_matrix = intensity_data(cube, noise_lim=noise_lim,
                                     p=p)

    else:
        raise NameError(
            "data_format must be either 'spectra' or 'intensity'.")

    return data_matrix
