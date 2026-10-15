"""Explicit device-service fixture. Actual native leases tested separately."""
class FixtureAdmission:
    expected=None
    retain=False
    def __enter__(self):return self
    def __exit__(self,*args):pass
