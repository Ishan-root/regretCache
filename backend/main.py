from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .simulate import simulate
from .workloads import generate

FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'frontend'

app = FastAPI(title='RegretCache')


class SimRequest(BaseModel):
    workload: Literal['zipf', 'loop', 'scan_hot', 'shifting'] = 'scan_hot'
    n_requests: int = Field(300, ge=20, le=1000)
    capacity: int = Field(8, ge=2, le=64)
    ghost_size: int = Field(8, ge=1, le=64)
    half_life: float = Field(100.0, gt=0, le=10000)
    seed: int = Field(42, ge=0, le=1000000)


@app.post('/api/simulate')
def api_simulate(req: SimRequest):
    trace = generate(req.workload, req.n_requests, req.seed)
    result = simulate(trace, req.capacity, req.ghost_size, req.half_life)
    result['workload'] = req.workload
    return result


@app.get('/api/health')
def health():
    return {'status': 'ok'}


# This mount must be the last statement. Mounted at '/', it would shadow routes added after it.
app.mount('/', StaticFiles(directory=FRONTEND_DIR, html=True), name='frontend')
