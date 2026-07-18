import os

from .. import schemas


def open_file(args: schemas.OpenFile) -> None:
    # args.path is already resolved and containment-checked by the validator
    os.startfile(args.path)
