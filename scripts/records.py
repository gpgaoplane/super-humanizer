
from dataclasses import dataclass, field


@dataclass
class Unit:

    id: str
    kind: str


    surface: str
    text: str
    locator: dict
    weighs: bool = True
    frame: dict | None = None


    @property
    def span(self):

        return (self.locator["start"], self.locator["end"])


@dataclass
class Document:
    path: str
    format: str
    units: list
    cannot_see: list
    encoding: str
    newline: str
    protected: list = field(default_factory=list)


    protected_names: list = field(default_factory=list)
    skipped: bool = False

    text: str = ""


    original_bytes: bytes = b""




@dataclass
class Finding:
    rule: str
    rulebook: str
    unit: str
    span: tuple | None
    tier: str
    source: str
    verdict: str
    fix: dict | None = None
    exception: str | None = None
    weight: str = "counted"
    category: str = ""
    twin: str = ""
    fid: str = ""
    second_reader: bool = False





    rewrite: str = ""




    meaning: str = ""


    risk: str = ""



def number(findings):

























    for i, f in enumerate(findings, start=1):
        f.fid = f"f{i:04d}"
    return findings


@dataclass
class DensityRecord:
    unit: str
    marks: int
    vocab: int
    dense: bool
