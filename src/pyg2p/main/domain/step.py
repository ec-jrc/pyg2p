class Step(object):
    def __init__(self, start_step, end_step, points_meridian, input_step):
        self.start_step = start_step
        self.end_step = end_step
        # spatial resolution
        self.resolution = points_meridian
        # temporal resolution
        self.input_step = input_step

    def __hash__(self):
        return hash((self.start_step, self.end_step, self.resolution, self.input_step))

    def __eq__(self, other):
        return (self.start_step, self.end_step, self.resolution, self.input_step) == (
               (other.start_step, other.end_step, other.resolution, other.input_step))

    def __str__(self):
        return 's:{} e:{} res:{} step-lenght:{}'.format(self.start_step, self.end_step, self.resolution, self.input_step)

    def __lt__(self, other):
        return self.start_step < other.start_step

    def __le__(self, other):
        return self.start_step < other.start_step
