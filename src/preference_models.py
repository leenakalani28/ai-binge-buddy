from typing import Literal
from pydantic import BaseModel, Field, field_validator

CONTENT = ["Movies", "TV Series", "Documentaries", "Documentary Series"]

class Preference(BaseModel):
    name: str
    content: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    providers: list[int] = Field(default_factory=list)
    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value or len(value) > 40:
            raise ValueError("Names must contain 1–40 characters.")
        return value

def validate_group(users):
    if not 1 <= len(users) <= 6:
        raise ValueError("Choose one to six people.")
    if len({u.name.casefold() for u in users}) != len(users):
        raise ValueError("Each person needs a different name.")

class Candidate(BaseModel):
    id: int
    media_type: Literal["movie", "tv"]
    title: str
    year: str = "Unknown"
    genres: list[str] = Field(default_factory=list)
    language: str = ""
    runtime: int | None = None
    seasons: int | None = None
    rating: float = 0
    votes: int = 0
    popularity: float = 0
    overview: str = "Synopsis unavailable."
    poster: str | None = None
    providers: dict[str, list[dict]] = Field(default_factory=dict)
    watch_link: str | None = None
    trailer: str | None = None
    cast: list[str] = Field(default_factory=list)
    makers: list[str] = Field(default_factory=list)

    @property
    def key(self):
        return f"{self.media_type}:{self.id}"

    @property
    def category(self):
        documentary = "Documentary" in self.genres
        return ("Documentaries" if documentary else "Movies") if self.media_type == "movie" else ("Documentary Series" if documentary else "TV Series")
