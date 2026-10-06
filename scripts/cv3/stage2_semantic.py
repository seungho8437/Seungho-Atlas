#!/usr/bin/env python3
"""Typed Stage 2 semantic execution framework.

This file defines execution states and family-level dispatch contracts only.
Individual acupoint IDs are deliberately forbidden from the registry.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from typing import Any,Callable

class ExecStatus(str,Enum):
 RESOLVED="RESOLVED"
 MULTIPLE="MULTIPLE"
 UNRESOLVED="UNRESOLVED"
 INVALID="INVALID"

@dataclass(frozen=True)
class ExecCandidate:
 geometry:Any
 provenance:dict
 residuals:dict=field(default_factory=dict)

@dataclass(frozen=True)
class ExecResult:
 status:ExecStatus
 candidates:tuple[ExecCandidate,...]
 executor:str
 reason:str|None=None

class SemanticRegistry:
 def __init__(self):
  self.landmark_executors:dict[str,Callable]={}
  self.relation_executors:dict[str,Callable]={}
  self.geometry_executors:dict[str,Callable]={}
  self.condition_executors:dict[str,Callable]={}
  self.measurement_executors:dict[str,Callable]={}

 def _register(self,table,key,fn):
  if not key or key.upper().startswith(("LU","LI","ST","SP","HT","SI","BL","KI","PC","TE","GB","LR","GV","CV")):
   raise ValueError(f"family registry key must not be an acupoint id: {key}")
  if key in table: raise ValueError(f"duplicate executor registration: {key}")
  table[key]=fn
  return fn

 def landmark(self,key):
  return lambda fn:self._register(self.landmark_executors,key,fn)
 def relation(self,key):
  return lambda fn:self._register(self.relation_executors,key,fn)
 def geometry(self,key):
  return lambda fn:self._register(self.geometry_executors,key,fn)
 def condition(self,key):
  return lambda fn:self._register(self.condition_executors,key,fn)
 def measurement(self,key):
  return lambda fn:self._register(self.measurement_executors,key,fn)

def unresolved(executor,reason,provenance=None):
 return ExecResult(ExecStatus.UNRESOLVED,tuple(),executor,reason)

def invalid(executor,reason,provenance=None):
 return ExecResult(ExecStatus.INVALID,tuple(),executor,reason)

def resolved(executor,geometry,provenance,residuals=None):
 return ExecResult(ExecStatus.RESOLVED,(ExecCandidate(geometry,provenance,residuals or {}),),executor,None)

def multiple(executor,candidates):
 return ExecResult(ExecStatus.MULTIPLE,tuple(candidates),executor,"multiple valid candidates; caller must not collapse arbitrarily")
