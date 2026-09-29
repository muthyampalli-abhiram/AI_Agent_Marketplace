import itertools
from typing import Any, Dict, List
import networkx as nx
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from app.models import Agent, TeamMembership


def build_collaboration_graph(db_session: Session) -> nx.Graph:
    """
    Build a NetworkX Graph where nodes are agent names with attributes
    (performance_score, total_tasks, total_failures) and edge weights
    represent co-occurrence in TaskRuns.
    """
    G = nx.Graph()

    agents = db_session.query(Agent).all()
    agent_id_map: Dict[str, str] = {}
    for agent in agents:
        agent_id_map[agent.id] = agent.name
        G.add_node(
            agent.name,
            performance_score=agent.performance_score if agent.performance_score is not None else 0.7,
            total_tasks=agent.total_tasks or 0,
            total_failures=agent.total_failures or 0,
            domain=agent.domain or "unknown",
        )

    memberships = db_session.query(TeamMembership).all()
    task_groups: Dict[str, List[str]] = {}
    for m in memberships:
        name = agent_id_map.get(m.agent_id)
        if name:
            if m.task_run_id not in task_groups:
                task_groups[m.task_run_id] = []
            if name not in task_groups[m.task_run_id]:
                task_groups[m.task_run_id].append(name)

    for task_run_id, agent_names in task_groups.items():
        if len(agent_names) > 1:
            for a, b in itertools.combinations(sorted(agent_names), 2):
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)

    return G


def render_collaboration_graph(graph: nx.Graph) -> str:
    """
    Render a NetworkX collaboration graph as a Plotly HTML visualization.
    Nodes are sized/colored by performance_score, edges weighted by co-occurrence.
    """
    if graph.number_of_nodes() == 0:
        return "<div>No agent nodes available in collaboration graph.</div>"

    pos = nx.spring_layout(graph, seed=42, k=0.8)

    edge_traces = []

    for edge in graph.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        weight = edge[2].get("weight", 1)

        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            line=dict(width=max(1, weight * 2), color="#888"),
            hoverinfo="none",
            mode="lines",
        )
        edge_traces.append(edge_trace)

    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []

    for node in graph.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        data = graph.nodes[node]
        perf = data.get("performance_score", 0.7)
        tasks = data.get("total_tasks", 0)
        failures = data.get("total_failures", 0)

        node_text.append(
            f"<b>Agent: {node}</b><br>"
            f"Domain: {data.get('domain')}<br>"
            f"Performance Score: {perf:.4f}<br>"
            f"Total Tasks: {tasks}<br>"
            f"Total Failures: {failures}"
        )
        node_color.append(perf)
        node_size.append(max(20, min(50, 20 + tasks * 3)))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=[n for n in graph.nodes()],
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale="Viridis",
            color=node_color,
            size=node_size,
            colorbar=dict(
                thickness=15,
                title="Performance Score",
                xanchor="left",
            ),
            line_width=2,
        ),
    )

    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            title=dict(text="<b>Agent Collaboration Network Graph</b>", font=dict(size=18)),
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=20, r=20, t=50),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            template="plotly_white",
        ),
    )

    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def render_task_run_summary(db_session: Session, task_run_id: str) -> str:
    """
    Render task run execution analytics as a Plotly bar chart (latency per agent)
    and an HTML details table underneath.
    """
    memberships = (
        db_session.query(TeamMembership)
        .filter(TeamMembership.task_run_id == task_run_id)
        .all()
    )

    if not memberships:
        return f"<div><h3>Task Run: {task_run_id}</h3><p>No team membership data recorded.</p></div>"

    agent_id_map = {a.id: a.name for a in db_session.query(Agent).all()}

    names = []
    latencies = []
    colors = []
    table_rows = []

    for m in memberships:
        agent_name = agent_id_map.get(m.agent_id, m.agent_id)
        latency = m.latency_ms or 0.0
        success = m.success if m.success is not None else True
        quality = m.quality_score if m.quality_score is not None else 0.6

        names.append(agent_name)
        latencies.append(latency)
        colors.append("#2ecc71" if success else "#e74c3c")

        status_badge = (
            "<span style='color: green; font-weight: bold;'>SUCCESS</span>"
            if success
            else "<span style='color: red; font-weight: bold;'>FAILED</span>"
        )
        table_rows.append(
            f"<tr>"
            f"<td style='padding: 8px; border: 1px solid #ddd;'>{agent_name}</td>"
            f"<td style='padding: 8px; border: 1px solid #ddd;'>{m.subtask or 'N/A'}</td>"
            f"<td style='padding: 8px; border: 1px solid #ddd;'>{status_badge}</td>"
            f"<td style='padding: 8px; border: 1px solid #ddd;'>{latency:.2f} ms</td>"
            f"<td style='padding: 8px; border: 1px solid #ddd;'>{quality:.2f}</td>"
            f"</tr>"
        )

    fig = go.Figure(
        data=[
            go.Bar(
                x=names,
                y=latencies,
                marker_color=colors,
                text=[f"{l:.1f} ms" for l in latencies],
                textposition="auto",
            )
        ],
        layout=go.Layout(
            title=f"<b>Task Run Latency per Agent ({task_run_id})</b>",
            xaxis_title="Agent Name",
            yaxis_title="Latency (ms)",
            template="plotly_white",
            margin=dict(b=40, l=40, r=40, t=50),
        ),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    table_html = f"""
    <div style="font-family: Arial, sans-serif; margin-top: 20px;">
        <h3>Task Run Execution Details ({task_run_id})</h3>
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 10px; border: 1px solid #ddd;">Agent Name</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Subtask</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Status</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Latency</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Quality Score</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>
    """

    return f"<div>{chart_html}{table_html}</div>"
