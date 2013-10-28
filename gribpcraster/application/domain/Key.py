__author__ = 'dominik'

class Key(object):

    def __init__(self, start_step_,end_step_,points_meridian_,input_step_):
        self.start_step=start_step_
        self.end_step=end_step_
        self.resolution=points_meridian_
        self.input_step=input_step_

    def __hash__(self):
        return hash((self.start_step, self.end_step,self.resolution, self.input_step))

    def __eq__(self, other):
        return (self.start_step, self.end_step,self.resolution, self.input_step)==((other.start_step, other.end_step,other.resolution, other.input_step))

    def split(self,c):
        return [self.start_step, self.end_step, self.resolution, self.input_step]

    def __str__(self):
        return 's:%d e:%d res:%d step-lenght:%d'%(int(self.start_step), int(self.end_step), int(self.resolution), int(self.input_step))