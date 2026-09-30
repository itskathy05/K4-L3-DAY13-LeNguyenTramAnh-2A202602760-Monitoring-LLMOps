"""Six-panel dashboard calculated from the application's JSONL event log."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .metrics import percentile

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "dashboard.yaml"


def _read_events(path: Path, start: datetime, end: datetime) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
                timestamp = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
                timestamp = timestamp.astimezone(timezone.utc)
            except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
                continue
            if start <= timestamp <= end:
                event["_minute"] = timestamp.replace(second=0, microsecond=0)
                events.append(event)
    return events


def _numbers(events: list[dict[str, Any]], field: str) -> list[float]:
    return [float(event[field]) for event in events if isinstance(event.get(field), (int, float)) and not isinstance(event.get(field), bool)]


def _pct(numerator: int, denominator: int) -> float | None:
    return round(numerator * 100 / denominator, 2) if denominator else None


def build_dashboard_snapshot(
    *, now: datetime | None = None, log_path: Path | None = None, config_path: Path = CONFIG_PATH
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = end - timedelta(minutes=config["time_range_minutes"])
    events = _read_events(log_path or Path(os.getenv("LOG_PATH", "data/logs.jsonl")), start, end)
    minutes: list[datetime] = []
    cursor = start.replace(second=0, microsecond=0)
    while cursor <= end:
        minutes.append(cursor)
        cursor += timedelta(minutes=1)
    by_minute: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_minute[event["_minute"]].append(event)

    requests = [event for event in events if event.get("event") == "request_received"]
    failures = [event for event in events if event.get("event") == "request_failed"]
    responses = [event for event in events if event.get("event") == "response_sent"]
    retrieval_events = [
        event for event in events
        if event.get("event") in {"response_sent", "request_failed"}
        and isinstance(event.get("tool_success"), bool)
    ]
    latency = _numbers(responses, "latency_ms")
    ttft = _numbers(responses, "ttft_ms")
    quality = _numbers(responses, "quality_score")
    cost = _numbers(responses, "cost_usd")
    tokens_in = _numbers(responses, "tokens_in")
    tokens_out = _numbers(responses, "tokens_out")
    breakdown = dict(sorted(Counter(str(event.get("error_type") or "unknown") for event in failures).items()))

    def series(value_fn):
        return [value_fn(by_minute[minute]) for minute in minutes]

    def of_type(bucket, name):
        return [event for event in bucket if event.get("event") == name]

    metrics: dict[str, tuple[dict[str, Any], dict[str, list[float | None]], float | None]] = {
        "latency": (
            {
                "P50": percentile(latency, 50) if latency else None,
                "P95": percentile(latency, 95) if latency else None,
                "P99": percentile(latency, 99) if latency else None,
                "TTFT P95": percentile(ttft, 95) if ttft else None,
            },
            {
                "P95": series(lambda bucket: percentile(_numbers(of_type(bucket, "response_sent"), "latency_ms"), 95) if _numbers(of_type(bucket, "response_sent"), "latency_ms") else None),
                "TTFT P95": series(lambda bucket: percentile(_numbers(of_type(bucket, "response_sent"), "ttft_ms"), 95) if _numbers(of_type(bucket, "response_sent"), "ttft_ms") else None),
            },
            3000,
        ),
        "traffic": (
            {"Requests": len(requests), "Average/min": round(len(requests) / config["time_range_minutes"], 2)},
            {"Requests/min": series(lambda bucket: len(of_type(bucket, "request_received")))},
            1,
        ),
        "errors": (
            {
                "Error rate": _pct(len(failures), len(requests)),
                "Errors": len(failures),
                "Retrieval success": _pct(sum(event["tool_success"] for event in retrieval_events), len(retrieval_events)),
                "Breakdown": breakdown,
            },
            {
                "Error rate": series(lambda bucket: _pct(len(of_type(bucket, "request_failed")), len(of_type(bucket, "request_received")))),
                "Retrieval success": series(lambda bucket: _pct(sum(event["tool_success"] for event in bucket if isinstance(event.get("tool_success"), bool)), sum(isinstance(event.get("tool_success"), bool) for event in bucket))),
            },
            2,
        ),
        "cost": (
            {"Total": round(sum(cost), 6)},
            {"USD/min": series(lambda bucket: round(sum(_numbers(of_type(bucket, "response_sent"), "cost_usd")), 6))},
            None,
        ),
        "tokens": (
            {"Input": int(sum(tokens_in)), "Output": int(sum(tokens_out))},
            {
                "Input": series(lambda bucket: int(sum(_numbers(of_type(bucket, "response_sent"), "tokens_in")))),
                "Output": series(lambda bucket: int(sum(_numbers(of_type(bucket, "response_sent"), "tokens_out")))),
            },
            None,
        ),
        "quality": (
            {"Mean": round(mean(quality), 3) if quality else None},
            {"Mean": series(lambda bucket: round(mean(values), 3) if (values := _numbers(of_type(bucket, "response_sent"), "quality_score")) else None)},
            0.75,
        ),
    }

    panels = []
    for panel_config in config["panels"]:
        panel_id = panel_config["id"]
        summary, chart_series, line_threshold = metrics[panel_id]
        if line_threshold is not None:
            line_threshold = panel_config["threshold"]["value"]
        panels.append({
            "id": panel_id,
            "title": panel_config["title"],
            "unit": panel_config["unit"],
            "threshold": panel_config["threshold"],
            "summary": summary,
            "series": chart_series,
            "line_threshold": line_threshold,
        })
    return {
        "title": config["title"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "time_range_minutes": config["time_range_minutes"],
        "refresh_seconds": config["refresh_seconds"],
        "bucket_times": [minute.isoformat() for minute in minutes],
        "event_count": len(events),
        "panels": panels,
    }


DASHBOARD_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Day 13 Monitoring Dashboard</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f7fb;color:#152238;margin:0;padding:24px}
header{max-width:1400px;margin:auto  auto 22px}h1{margin:0 0 8px;font-size:28px}p{margin:4px 0;color:#4d5d75}
#grid{max-width:1400px;margin:auto;display:grid;grid-template-columns:repeat(2,minmax(360px,1fr));gap:18px}
.card{background:white;border:1px solid #d9e2ed;border-radius:12px;padding:18px;box-shadow:0 3px 12px #10253d0d}
.card h2{font-size:18px;margin:0 0 10px}.metrics{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px}
.metric{border-radius:8px;background:#edf3fa;padding:8px 10px;font-size:13px}.metric strong{display:block;font-size:18px}
.threshold{font-size:12px;color:#9a4b16;margin-bottom:8px}.chart{width:100%;height:150px;background:#fbfcff;border:1px solid #edf0f5;border-radius:6px}
.legend{font-size:12px;color:#4d5d75;margin-top:6px}.empty{padding:12px;color:#8b4d1d;background:#fff3df;border-radius:8px}
@media(max-width:850px){#grid{grid-template-columns:1fr}body{padding:12px}}
</style></head><body><header><h1 id="title">Monitoring dashboard</h1><p id="range">Loading...</p><p id="status"></p></header>
<main id="grid"></main>
<script>
const colors=['#2463d3','#db7d21','#2c9276']; const ns='http://www.w3.org/2000/svg';
function el(tag,attrs){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n;}
function fmt(v){if(v===null||v===undefined)return 'n/a';if(typeof v==='object')return Object.entries(v).map(([k,x])=>`${k}: ${x}`).join(', ')||'none';return String(v);}
function draw(svg,series,threshold){const entries=Object.entries(series);const all=entries.flatMap(([,vals])=>vals.filter(v=>typeof v==='number'));
 if(threshold!==null)all.push(threshold);const min=Math.min(0,...all),max=Math.max(1,...all),span=max-min||1;
 const y=v=>130-(v-min)/span*112; svg.appendChild(el('line',{x1:28,y1:130,x2:580,y2:130,stroke:'#aab7c8'}));
 if(threshold!==null){const yy=y(threshold);svg.appendChild(el('line',{x1:28,y1:yy,x2:580,y2:yy,stroke:'#bf442d','stroke-dasharray':'5 4'}));}
 entries.forEach(([name,vals],idx)=>{let points=[];vals.forEach((v,i)=>{if(typeof v==='number'){points.push([28+i*552/Math.max(1,vals.length-1),y(v)]);}else if(points.length){if(points.length>1)svg.appendChild(el('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:colors[idx%colors.length],'stroke-width':2}));points=[];}});
 if(points.length>1)svg.appendChild(el('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:colors[idx%colors.length],'stroke-width':2}));});}
function render(data){document.getElementById('title').textContent=data.title;document.getElementById('range').textContent=`UTC ${data.start} → ${data.end} | ${data.time_range_minutes} min | refresh ${data.refresh_seconds}s`;
 document.getElementById('status').textContent=`${data.event_count} log events in window`;
 const grid=document.getElementById('grid');grid.replaceChildren();if(!data.event_count){const note=document.createElement('p');note.className='empty';note.textContent='No events in this time range. Run the load test and refresh.';grid.appendChild(note);}
 data.panels.forEach(p=>{const card=document.createElement('section');card.className='card';const title=document.createElement('h2');title.textContent=p.title;card.appendChild(title);
 const metricBox=document.createElement('div');metricBox.className='metrics';for(const [k,v] of Object.entries(p.summary)){const box=document.createElement('div');box.className='metric';const label=document.createElement('span');label.textContent=k;const value=document.createElement('strong');value.textContent=fmt(v);box.append(label,value);metricBox.appendChild(box);}card.appendChild(metricBox);
 const threshold=document.createElement('div');threshold.className='threshold';threshold.textContent=`Unit: ${p.unit} | threshold: ${p.threshold.aggregation} ${p.threshold.operator} ${p.threshold.value}`;card.appendChild(threshold);
 const svg=el('svg',{viewBox:'0 0 600 150',class:'chart',role:'img','aria-label':p.title});draw(svg,p.series,p.line_threshold);card.appendChild(svg);
 const legend=document.createElement('div');legend.className='legend';legend.textContent=Object.keys(p.series).join('  •  ');card.appendChild(legend);grid.appendChild(card);});}
async function refresh(){try{const response=await fetch('/dashboard/data',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();render(data);setTimeout(refresh,data.refresh_seconds*1000);}catch(err){document.getElementById('status').textContent=`Dashboard error: ${err.message}`;setTimeout(refresh,30000);}}
refresh();
</script></body></html>"""
