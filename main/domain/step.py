class Step(object):
    def __init__(self, start_step_, end_step_, points_meridian_, input_step_):
        self.start_step = start_step_
        self.end_step = end_step_
        # spatial resolution
        self.resolution = points_meridian_
        # temporal resolution
        self.input_step = input_step_

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
