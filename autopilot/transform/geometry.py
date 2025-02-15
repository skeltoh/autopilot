import typing
from time import time

import numpy as np
from scipy.spatial import distance
from scipy.spatial.transform import Rotation as R
from scipy.optimize import curve_fit

from autopilot.transform.transforms import Transform
from autopilot.transform.timeseries import Kalman


class Distance(Transform):
    """
    Given an n_samples x n_dimensions array, compute pairwise or mean distances
    """
    format_in = {'type': np.ndarray}
    format_out = {'type': np.ndarray}

    def __init__(self,
                 pairwise: bool=False,
                 n_dim: int = 2,
                 metric: str='euclidean',
                 squareform: bool=True,
                 *args, **kwargs):
        """

        Args:
            pairwise (bool): If False (default), return mean distance. if True, return all distances
            n_dim (int): number of dimensions (input array will be filtered like ``input[:,0:n_dim]``
            metric (str): any metric acceptable to :func:`scipy.spatial.distance.pdist
            squareform (bool): if pairwise is True, if True return square distance matrix, otherwise return compressed distance matrix (dist(X[i], X[j] = y[i*j])
            *args:
            **kwargs:
        """

        super(Distance, self).__init__(*args, **kwargs)

        self.pairwise = pairwise
        self.n_dim = n_dim
        self.metric = metric
        self.squareform = squareform

    def process(self, input: np.ndarray):

        # filter to input_dimension
        input = input[:,0:self.n_dim]

        output = distance.pdist(input, metric=self.metric)

        if self.pairwise:
            if self.squareform:
                output = distance.squareform(output)
        else:
            output = np.mean(output)

        return output


class Angle(Transform):
    """
    Get angle between line formed by two points and horizontal axis
    """

    format_in = {'type': np.ndarray}
    format_out = {'type': float}

    def __init__(self, abs=True, degrees=True, *args, **kwargs):
        super(Angle, self).__init__(*args, **kwargs)
        self.abs = abs
        self.degrees = degrees

    def process(self, input):
        angle = np.arctan2(input[1][1]-input[0][1], input[1][0]-input[0][0])
        if self.abs:
            angle += np.pi
        if self.degrees:
            angle = angle*(180/np.pi)
        return angle


class IMU_Orientation(Transform):
    """
    Compute absolute orientation (roll, pitch) from accelerometer and gyroscope measurements
    (eg from :class:`.hardware.i2c.I2C_9DOF` )

    Uses a :class:`.timeseries.Kalman` filter, and implements :cite:`patonisFusionMethodCombining2018a` to fuse
    the sensors

    Can be used with accelerometer data only, or with combined accelerometer/gyroscope data for
    greater accuracy

    Arguments:
        invert_gyro (bool): if the gyroscope's orientation is inverted from accelerometer measurement, multiply
            gyro readings by -1 before using
        use_kalman (bool): Whether to use kalman filtering (True, default), or return raw trigonometric
            transformation of accelerometer readings (if provided, gyroscope readings will be ignored)

    Attributes:
        kalman (:class:`.transform.timeseries.Kalman`): If ``use_kalman == True`` , the Kalman Filter.

    References:
        :cite:`patonisFusionMethodCombining2018a`
        :cite:`abyarjooImplementingSensorFusion2015`
    """

    def __init__(self, use_kalman:bool = True, invert_gyro:bool=False, *args, **kwargs):
        super(IMU_Orientation, self).__init__(*args, **kwargs)

        self.invert_gyro = invert_gyro # type: bool
        self._last_update = None # type: typing.Optional[float]
        self._dt = 0 # type: float
        # preallocate orientation array for filtered values
        self.orientation = np.zeros((2), dtype=float) # type: np.ndarray
        # and for unfiltered values so they aren't ambiguous
        self._orientation = np.zeros((2), dtype=float)  # type: np.ndarray

        self.kalman = None # type: typing.Optional[Kalman]
        if use_kalman:
            self.kalman = Kalman(dim_state=2, dim_measurement=2, dim_control=2)  # type: typing.Optional[Kalman]

    def process(self, accelgyro:typing.Union[typing.Tuple[np.ndarray, np.ndarray], np.ndarray]) -> np.ndarray:
        """

        Args:
            accelgyro (tuple, :class:`numpy.ndarray`): tuple of (accelerometer[x,y,z], gyro[x,y,z]) readings as arrays, or
                an array of just accelerometer[x,y,z]

        Returns:
            :class:`numpy.ndarray`: filtered [roll, pitch] calculations in degrees
        """
        # check what we were given...
        if isinstance(accelgyro, (tuple, list)) and len(accelgyro) == 2:
            # combined accelerometer and gyroscope readings
            accel, gyro = accelgyro
        elif isinstance(accelgyro, np.ndarray) and np.squeeze(accelgyro).shape[0] == 3:
            # just accelerometer readings
            accel = accelgyro
            gyro = None
        else:
            # idk lol
            self.logger.exception(f'Need input to be a tuple of accelerometer and gyroscope readings, or an array of accelerometer readings. got {accelgyro}')
            return

        # convert accelerometer readings to roll and pitch
        pitch = 180*np.arctan2(accel[0], np.sqrt(accel[1]**2 + accel[2]**2))/np.pi
        roll = 180*np.arctan2(accel[1], np.sqrt(accel[0]**2 + accel[2]**2))/np.pi


        if self.kalman is None:
            # store orientations in external attribute if not using kalman filter
            self.orientation[:] = (roll, pitch)
            return self.orientation.copy()
        else:
            # if using kalman filter, use private array to store raw orientation
            self._orientation[:] = (roll, pitch)

        # TODO: Don't assume that we're fed samples instantatneously -- ie. once data representations are stable, need to accept a timestamp here rather than making one
        if self._last_update is None or gyro is None:
            # first time through don't have dt to scale gyro by
            self.orientation[:] = np.squeeze(self.kalman.process(self._orientation))
            self._last_update = time()

        else:
            if self.invert_gyro:
                gyro *= -1

            # get dt for time since last update
            update_time = time()
            self._dt = update_time-self._last_update
            self._last_update = update_time

            if self._dt>1:
                # if it's been really long, the gyro read is pretty much useless and will give ridiculous reads
                self.orientation[:] = np.squeeze(self.kalman.process(self._orientation))
            else:
                # run predict and update stages separately to incorporate gyro
                self.kalman.predict(u=gyro[0:2]*self._dt)
                self.orientation[:] = np.squeeze(self.kalman.update(self._orientation))

        return self.orientation.copy()


class Rotate(Transform):
    """
    Rotate in 3 dimensions using :class:`scipy.spatial.transform.Rotation`

    Args:
        dims ( "xyz" ): string specifying which axes the rotation will be around, eg ``"xy"`` , ``"xyz"```
        rotation_type (str): Format of rotation input, must be one available to the :class:`~scipy.spatial.transform.Rotation` class
            (but currently only euler angles are supported)
        degrees (bool): whether to output rotation in degrees (True, default) or radians
        inverse ("xyz"): dimensions in the "rotation" input to :meth:`.Rotate.process` to inverse before applying rotation
        rotation (tuple, list, :class:`numpy.ndarray`, None): If supplied, use the same rotation for all processed data. If None,
            :meth:`.Rotate.process` will expect a tuple of (data, rotation).
    """

    _DIMS = {
        'x': 0,
        'y': 1,
        'z': 2
    }

    def __init__(self, dims="xyz", rotation_type="euler", degrees=True, inverse="", rotation=None, *args, **kwargs):
        super(Rotate, self).__init__(*args, **kwargs)

        self.degrees = degrees
        self.rotation_type = rotation_type

        # parse dimensions and inverse into slices
        if not dims:
            e = ValueError('need to provide some dimensino to rotate around, got empty dims')
            self.logger.exception(e)
            raise e

        # store dims and something we can slice with for dims and inverse
        self.dims = dims
        self._dims = [self._DIMS[dim] for dim in dims]

        if not inverse:
            self.inverse = False
            self._inverse = None
        else:
            self.inverse = inverse
            self._inverse = [self._DIMS[dim] for dim in inverse]

        # stash rotation creation method depending on rotation_type
        if rotation_type == "euler":
            self._rotate_constructor = R.from_euler
        else:
            e = NotImplementedError('Only euler is implemented currently!')
            self.logger.exception(e)
            raise e

        # if we were provided an initial rotation, instantiate rotation here
        if rotation:
            # inverse what must be inverted
            if self.inverse:
                rotation[self._inverse] *= -1
            self._rotation = rotation
            self._rotator = self._rotate_constructor(self.dims, self._rotation, degrees=self.degrees)
        else:
            self._rotation = None
            self._rotator = None

    def process(self, input):
        """


        Args:
            input (tuple, :class:`numpy.ndarray`): a tuple of (input[x,y,z], rotation[x,y,z]) where input is to be rotated
                according to the axes in rotation (indicated in :attr:`.Rotate.dims` ). If only an input array is provided,
                a static rotation array must have been provided in the constructor (otherwise the most recent rotation will be used)

        Returns:
            :class:`numpy.ndarray` - rotated input array
        """

        if isinstance(input, (tuple, list)) and len(input) == 2:
            # split out input coords and rotation
            input, rotate = input

            # invert what must be inverted
            if self.inverse:
                rotate[self._inverse] *= -1

        else:
            rotate = None

        # if given a new rotation, use it
        if rotate is not None and (self._rotation is None or not np.array_equal(rotate, self._rotation)):
            self._rotator = self._rotate_constructor(self.dims, rotate, degrees=self.degrees)
            self._rotation = rotate

        # apply itttt and return
        try:
            return self._rotator.apply(input)
        except AttributeError:
            if self._rotator is None:
                e = RuntimeError('No rotation was provided, and none is available!')
                self.logger.exception(e)
                raise e

class Spheroid(Transform):
    """
    Fit and transform 3d coordinates according to some spheroid.

    Eg. for calibrating accelerometer readings by transforming them from their uncalibrated spheroid to the expected
    sphere with radius == 9.8m/s/s centered at (0,0,0).

    Does not estimate/correct for rotation of the spheroid.

    Examples:

        .. code-block:: python

            # Calibrate an accelerometer by transforming
            # readings to a 9.8-radius sphere centered at 0
            >>> sphere = Spheroid(target=(9.8,9.8,9.8,0,0,0))

            # take some readings...
            # imagine we're taking them from some sensor idk
            # say our sensor slightly exaggerates gravity
            # in the z-axis...
            >>> readings = np.array((0.,0.,10.5))

            # fit our object (need >>1 sample)
            >>> sphere.fit(readings)

            # transform to proper gravity
            >>> sphere.process(readings)
            [0., 0., 9.8]

    Args:
        target (tuple): parameterization of spheroid to transform to, if none is passed, transform to unit circle
            centered at (0,0,0). parameterized as::

            (a, # radius of x dimension
            b, # radius of y dimension
            c, # radius of z dimension
            x, # x-offset
            y, # y-offset
            z) # z-offset

        source (tuple): parameterization of spheroid to transform from in the same 6-tuple form as ``target``,
            if None is passed, assume we will use :meth:`.Spheroid.fit`
        fit (None, :class:`numpy.ndarray`): Initialize with values to fit, if None assume fit will be called later.


    References:
        * https://jekel.me/2020/Least-Squares-Ellipsoid-Fit/
        * http://www.juddzone.com/ALGORITHMS/least_squares_3D_ellipsoid.html
    """

    def __init__(self, target=(1,1,1,0,0,0),
                 source:tuple=(None, None, None, None, None, None),
                 fit:typing.Optional[np.ndarray]=None,
                 *args, **kwargs):
        super(Spheroid, self).__init__(*args, **kwargs)

        self.target = target
        self.source  = source

        self._scale = None
        self._offset_source = None
        self._offset_target = None
        self._update_arrays()

        if fit is not None:
            self.fit(fit, **kwargs)

    def _update_arrays(self):
        if not any([val is None for val in self.source]):
            self._scale = np.array((self.target[0]/self.source[0],
                                    self.target[1]/self.source[1],
                                    self.target[2]/self.source[2]))
            self._offset_source = np.array((self.source[3], self.source[4], self.source[5]))
            self._offset_target = np.array((self.target[3], self.target[4], self.target[5]))

    def fit(self, points, **kwargs):
        """
        Fit a spheroid from a set of noisy measurements

        updates the :attr:`._scale` and :attr:`._offset` private arrays used to manipulate input data

        .. note::

            It's usually important to pass ``bounds`` to :func:`scipy.optimize.curve_fit` !!! passed as a 2-tuple
            of ``((min_a, min_b, ...), (max_a, max_b...))`` In particular such that a, b, and c are positive. If no
            bounds are passed, assume at least that much.

        Args:
            points (:class:`numpy.ndarray`): (M, 3) array of points to fit
            **kwargs (): passed on to :func:`scipy.optimize.curve_fit`

        Returns:
            tuple: parameters of fit ellipsoid (a,b,c,x,y,z)
        """
        if 'bounds' in kwargs.keys():
            bounds = kwargs.pop('bounds')
        else:
            bounds = ((0,      0,      0,      -np.inf, -np.inf, -np.inf),
                      (np.inf, np.inf, np.inf,  np.inf,  np.inf,  np.inf))

        y = np.ones((points.shape[0]))
        parameters, _ = curve_fit(_ellipsoid_func, points, y, bounds=bounds, **kwargs)
        self.source = parameters
        self._update_arrays()

    def process(self, input:np.ndarray):
        """
        Transform input (x,y,z) points such that points in :attr:`.source` are mapped to those in :attr:`.target`

        Args:
            input (:class:`numpy.ndarray`): x, y, and z coordinates

        Returns:
            :class:`numpy.ndarray` : coordinates transformed according to the spheroid requested
        """
        if self._scale is None or self._offset_target is None or self._offset_source is None:
            self.logger.exception('process called without fit being performed or source ellipsoid provided! returning untransformed points!')
            return input

        # move to the center, then scale, then offset.

        return ((input - self._offset_source) * self._scale) + self._offset_target

    def generate(self, n:int, which:str='source', noise:float=0):
        """
        Generate random points from the ellipsoid

        Args:
            n (int): number of points to generate
            which ('str'): which spheroid to generate from? ('source' - default, or 'target')
            noise (float): noise to add to points

        Returns:
            :class:`numpy.ndarray` : (n, 3) array of generated points
        """
        if which == "source":
            if not any([val is None for val in self.source]):
                a,b,c,x,y,z = self.source
            else:
                self.logger.exception('Cannot generate from source, dont have ellipsoid parameterization')
                return
        elif which == "target":
            a, b, c, x, y, z = self.target
        else:
            self.logger.exception(f"Dont know how to generate points for which == {which}")
            return

        u = np.random.rand(n)
        v = np.random.rand(n)
        theta = u * 2.0 * np.pi
        phi = np.arccos(2.0 * v - 1.0)
        sinTheta, cosTheta = np.sin(theta), np.cos(theta)
        sinPhi,   cosPhi   = np.sin(phi),   np.cos(phi)
        rx = (a * sinPhi * cosTheta) + x + (np.random.rand(n) * noise)
        ry = (b * sinPhi * sinTheta) + y + (np.random.rand(n) * noise)
        rz = (c * cosPhi) + z + (np.random.rand(n) * noise)
        return np.column_stack((rx, ry, rz))



def _ellipsoid_func(fit, a, b, c, x, y, z):
    """
    Ellipsoid equation for use with :meth:`.Ellipsoid.fit`

    Args:
        fit (:class:`numpy.ndarray`): (M, 3) array of x,y,z points to fit
        a (float): X-scale parameter to fit
        b (float): Y-scale parameter to fit
        c (float): Z-scale parameter to fit
        x (float): X-offset parameter to fit
        y (float): Y-offset parameter to fit
        z (float): Z-offset parameter to fit

    Returns:
        float: result of ellipsoid function, minimize parameters to == 1
    """
    x_fit, y_fit, z_fit = fit[:,0], fit[:,1], fit[:,2]
    return ((x_fit - x)**2 / a**2) + ((y_fit - y)**2 / b**2) + ((z_fit - z)**2 / c**2)













