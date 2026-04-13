#!/bin/bash
set -e

if [ ! -f ".env.dev" ]; then
  cp .env.example .env.dev
  echo ".env.dev created from .env.example"
else
  echo ".env.dev already exists"
fi