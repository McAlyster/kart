""" Class representing a needed content correction """

class Correction :

    # Raw data
    raw = ""
    # Suggested Correction
    correct = ""
    # Model
    model = ""
    # field
    field = ""

    def __init__(self, raw, correct):
        self.raw = raw
        self.correct = correct

        print(f"Correction needed '{raw}' to '{correct}'")



    def keep_raw(self, store=False) :
        """ Set the raw version as correct and store it.

        Args :
            store (bool) : If True, update the database with new raw version (overrides the former value), defaults to False

        Return :
            None
        """

        self.correct = self.raw

        if store :
            self.save()

    def save(self) :
        """ Save the correct version to database. """
        print('SAVING TO DATABASE ------ TODO')
        pass
