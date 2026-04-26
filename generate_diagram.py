import os, textwrap, math, json, pathlib, datetime, re
out_dir="/mnt/data"
os.makedirs(out_dir, exist_ok=True)

def svg_header(w,h):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <style><![CDATA[
      .bg {{ fill: #ffffff; }}
      .box {{ fill: #ffffff; stroke: #111111; stroke-width: 2; rx: 18; ry: 18; }}
      .box2 {{ fill: #ffffff; stroke: #111111; stroke-width: 2; rx: 14; ry: 14; }}
      .mutebox {{ fill: #ffffff; stroke: #6b7280; stroke-width: 2; stroke-dasharray: 6 6; rx: 18; ry: 18; }}
      .title {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 28px; font-weight: 700; fill: #111111; }}
      .label {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 18px; font-weight: 600; fill: #111111; }}
      .small {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #111111; }}
      .mutetext {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #6b7280; }}
      .arrow {{ stroke: #111111; stroke-width: 2.5; fill: none; }}
      .arrowMuted {{ stroke: #6b7280; stroke-width: 2.5; fill: none; }}
      .thin {{ stroke: #111111; stroke-width: 2; fill: none; }}
      .dot {{ fill: #111111; }}
    ]]></style>
    <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#111111"/>
    </marker>
    <marker id="arrowheadMuted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280"/>
    </marker>
  </defs>
  <rect class="bg" x="0" y="0" width="{w}" height="{h}"/>
'''
def svg_footer():
    return "</svg>\n"

def box(x,y,w,h,cls="box",label="",sub=None,center=True):
    # returns svg snippet for rounded rect with label lines
    tx = x + w/2 if center else x+18
    ty = y + h/2
    lines=[]
    if label:
        lines.append(f'<text class="label" x="{tx}" y="{ty-2}" text-anchor="middle" dominant-baseline="middle">{label}</text>')
    if sub:
        lines.append(f'<text class="mutetext" x="{tx}" y="{ty+22}" text-anchor="middle" dominant-baseline="middle">{sub}</text>')
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" />\n' + "\n".join(lines) + "\n"

def title(x,y,text):
    return f'<text class="title" x="{x}" y="{y}">{text}</text>\n'

def arrow(x1,y1,x2,y2,muted=False):
    m = "arrowMuted" if muted else "arrow"
    marker = "arrowheadMuted" if muted else "arrowhead"
    return f'<path class="{m}" d="M {x1} {y1} L {x2} {y2}" marker-end="url(#{marker})"/>\n'

def arrow_curve(x1,y1,cx,cy,x2,y2,muted=False):
    m = "arrowMuted" if muted else "arrow"
    marker = "arrowheadMuted" if muted else "arrowhead"
    return f'<path class="{m}" d="M {x1} {y1} Q {cx} {cy} {x2} {y2}" marker-end="url(#{marker})"/>\n'

# Diagram 1: Inference API Architecture
w,h=1600,900
svg = svg_header(w,h)
svg += title(60,80,"AI Inference API · Reference Architecture")

# main flow boxes
y=220
box_w=250; box_h=90
x_positions=[90, 410, 730, 1050, 1370]
labels=[("Client","Browser · App"),("API Gateway","Auth · Rate limit"),("FastAPI Service","Validation · Routing"),("Model Runtime","CPU/GPU inference"),("Response","JSON · Stream")]
for x,(lab,subt) in zip(x_positions,labels):
    svg += box(x,y,box_w,box_h,"box",lab,subt)

# arrows between
for i in range(len(x_positions)-1):
    svg += arrow(x_positions[i]+box_w, y+box_h/2, x_positions[i+1], y+box_h/2)

# side boxes: Cache, Feature Store, Observability
svg += box(730,370,250,80,"box2","Redis Cache","Optional · hot keys")
svg += arrow_curve(855,310,855,340,855,370,muted=True)
svg += arrow_curve(855,450,855,340,855,310,muted=True)

svg += box(1050,370,250,80,"box2","Feature Store","Online features")
svg += arrow_curve(1175,310,1175,340,1175,370,muted=True)

svg += box(410,520,250,90,"mutebox","Observability","Logs · Metrics · Traces")
# arrows to observability from gateway and service
svg += arrow_curve(535,310,500,420,535,520,muted=True)
svg += arrow_curve(855,310,720,420,535,520,muted=True)

# versioning note
svg += '<text class="small" x="90" y="170">Endpoints: /v1/predict · /v2/predict · /health · /metrics</text>\n'
svg += '<text class="mutetext" x="90" y="195">Principle: stateless services · model loads once per worker · typed I/O contracts</text>\n'

svg += svg_footer()
path1=os.path.join(out_dir,"diagram_inference_api_architecture.svg")
with open(path1,"w",encoding="utf-8") as f:
    f.write(svg)

# Diagram 2: Container + Cloud Deployment
w,h=1600,900
svg = svg_header(w,h)
svg += title(60,80,"Containerized Deployment · Scalable Pattern")

# left: Dev
svg += '<text class="small" x="90" y="150">Build</text>\n'
svg += box(90,180,300,90,"box","Repo","FastAPI · Dockerfile")
svg += box(90,300,300,90,"box2","CI Pipeline","Tests · Build image")
svg += arrow(240,270,240,300)

svg += box(90,450,300,90,"box2","Container Registry","ECR · Docker Hub")
svg += arrow(240,390,240,450)

# right: Cloud cluster dashed
svg += '<text class="small" x="520" y="150">Run</text>\n'
svg += '<rect class="mutebox" x="520" y="180" width="1020" height="620" />\n'
svg += '<text class="label" x="540" y="220" text-anchor="start">Compute Platform</text>\n'
svg += '<text class="mutetext" x="540" y="248" text-anchor="start">ECS/Fargate · Kubernetes · VM Autoscaling</text>\n'

# inside cluster
svg += box(580,300,260,90,"box","Load Balancer","ALB · NGINX")
svg += box(910,280,260,90,"box","Service A","FastAPI workers")
svg += box(910,400,260,90,"box","Service B","FastAPI workers")
svg += box(1240,340,260,90,"box2","Redis","Cache · rate data")
svg += box(910,540,260,90,"box2","Monitoring","Prometheus · Grafana")
svg += box(1240,540,260,90,"box2","Logging","CloudWatch · ELK")

# arrows inside
svg += arrow(840,345,910,325)  # LB to svc A
svg += arrow(840,345,910,445)  # LB to svc B
svg += arrow_curve(1040,325,1180,290,1240,385,muted=True) # svc A to redis
svg += arrow_curve(1040,445,1180,470,1240,385,muted=True) # svc B to redis
svg += arrow_curve(1040,325,1040,480,1040,540,muted=True) # svc A to monitoring
svg += arrow_curve(1040,445,1040,520,1040,540,muted=True) # svc B to monitoring
svg += arrow_curve(1040,325,1180,500,1240,585,muted=True) # svc A to logging
svg += arrow_curve(1040,445,1180,520,1240,585,muted=True) # svc B to logging

# pipeline arrow from registry to cluster
svg += arrow(390,495,520,495)

# autoscaling note
svg += '<text class="mutetext" x="540" y="770" text-anchor="start">Autoscale on: CPU/GPU util · QPS · P95 latency · queue depth</text>\n'
svg += svg_footer()
path2=os.path.join(out_dir,"diagram_container_cloud_deployment.svg")
with open(path2,"w",encoding="utf-8") as f:
    f.write(svg)

# Diagram 3: Real-time Streaming (WebSockets / SSE)
w,h=1600,900
svg = svg_header(w,h)
svg += title(60,80,"Real-Time Streaming Inference · Web App Pattern")

# boxes: Browser, WebSocket/SSE, API, Generator, Client UI
svg += box(120,240,280,90,"box","Browser UI","React · JS")
svg += box(480,240,280,90,"box","Stream Channel","WebSocket · SSE")
svg += box(840,240,280,90,"box","FastAPI","/stream")
svg += box(1200,240,280,90,"box","Token Generator","LLM · model")
for x1,x2 in [(400,480),(760,840),(1120,1200)]:
    svg += arrow(x1,285,x2,285)

# downward: UI updates
svg += box(120,420,280,90,"box2","Render Loop","Append tokens")
svg += arrow_curve(260,330,260,375,260,420,muted=True)

# backpressure + buffers
svg += box(840,420,280,90,"box2","Back-pressure","Buffers · rate control")
svg += arrow_curve(980,330,980,375,980,420,muted=True)

# observability
svg += box(480,600,280,90,"mutebox","Observability","Latency · drops")
svg += arrow_curve(620,330,560,470,620,600,muted=True)
svg += arrow_curve(980,510,760,560,620,600,muted=True)

# notes
svg += '<text class="small" x="120" y="170">Goal: reduce perceived latency by returning partial outputs early</text>\n'
svg += '<text class="mutetext" x="120" y="195">Use streaming when response size is large or generation is incremental</text>\n'

svg += svg_footer()
path3=os.path.join(out_dir,"diagram_realtime_streaming_inference.svg")
with open(path3,"w",encoding="utf-8") as f:
    f.write(svg)

[path1, path2, path3]

