from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedImport(BaseModel):
    module: str


class ParsedFunction(BaseModel):
    name: str


class ParsedFileSignals(BaseModel):
    path: str
    language: str = "python"
    imports: list[ParsedImport] = Field(default_factory=list)
    functions: list[ParsedFunction] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class ParserRunResult(BaseModel):
    backend_id: str
    backend_version: str
    files: list[ParsedFileSignals] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
