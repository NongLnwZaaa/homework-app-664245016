from __future__ import annotations
from typing import Any
import streamlit as st
from neo4j import GraphDatabase, RoutingControl

def _config() -> tuple[str, str, str, str]:
    cfg = st.secrets["neo4j"]
    return (
        cfg["uri"],
        cfg["username"],
        cfg["password"],
        cfg.get("database", "neo4j"),
    )

@st.cache_resource(show_spinner=False)
def get_driver():
    uri, username, password, _ = _config()
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    return driver

def query(cypher: str, parameters: dict[str, Any] | None = None, *, write: bool = False) -> list[dict[str, Any]]:
    _, _, _, database = _config()
    records, _, _ = get_driver().execute_query(
        cypher,
        parameters_=parameters or {},
        database_=database,
        routing_=RoutingControl.WRITE if write else RoutingControl.READ,
    )
    return [record.data() for record in records]

def ping() -> bool:
    rows = query("RETURN 1 AS ok")
    return bool(rows and rows[0]["ok"] == 1)

def create_schema() -> None:
    statements = [
        "CREATE CONSTRAINT user_name_unique IF NOT EXISTS FOR (u:User) REQUIRE u.name IS UNIQUE",
        "CREATE CONSTRAINT song_title_unique IF NOT EXISTS FOR (s:Song) REQUIRE s.title IS UNIQUE",
    ]
    for stmt in statements:
        query(stmt, write=True)

def seed_demo_data() -> None:
    create_schema()
    
    songs = [
        "Bohemian Rhapsody", "Shape of You", "Blinding Lights", "Hotel California",
        "Rolling in the Deep", "Watermelon Sugar", "Billie Jean", "Hey Jude",
        "Uptown Funk", "Smells Like Teen Spirit", "Thinking Out Loud", 
        "Someone Like You", "Perfect", "Dance Monkey", "Let It Be",
        "Yesterday", "Havana", "Bad Guy", "Wonderwall", "Hallelujah"
    ]
    
    users = [
        "Alice", "Bob", "Charlie", "David", "Eve",
        "Frank", "Grace", "Heidi", "Ivan", "Judy"
    ]
    
    likes = [
        ("Alice", "Bohemian Rhapsody"), ("Alice", "Hotel California"), ("Alice", "Hey Jude"),
        ("Bob", "Shape of You"), ("Bob", "Watermelon Sugar"), ("Bob", "Uptown Funk"),
        ("Charlie", "Blinding Lights"), ("Charlie", "Watermelon Sugar"), ("Charlie", "Bad Guy"),
        ("David", "Hotel California"), ("David", "Smells Like Teen Spirit"), ("David", "Wonderwall"),
        ("Eve", "Rolling in the Deep"), ("Eve", "Someone Like You"), ("Eve", "Hallelujah"),
        ("Frank", "Shape of You"), ("Frank", "Perfect"), ("Frank", "Thinking Out Loud"),
        ("Grace", "Billie Jean"), ("Grace", "Uptown Funk"), ("Grace", "Bohemian Rhapsody"),
        ("Heidi", "Dance Monkey"), ("Heidi", "Havana"), ("Heidi", "Bad Guy"),
        ("Ivan", "Let It Be"), ("Ivan", "Yesterday"), ("Ivan", "Hey Jude"),
        ("Judy", "Hallelujah"), ("Judy", "Yesterday"), ("Judy", "Rolling in the Deep"), ("Judy", "Perfect")
    ]

    query("UNWIND $rows AS name MERGE (u:User {name: name})", {"rows": users}, write=True)
    query("UNWIND $rows AS title MERGE (s:Song {title: title})", {"rows": songs}, write=True)
    query(
        """
        UNWIND $rows AS row
        MATCH (u:User {name: row[0]}), (s:Song {title: row[1]})
        MERGE (u)-[:LIKES]->(s)
        """,
        {"rows": likes}, write=True
    )

# --- READ ---
def get_users() -> list[dict[str, Any]]:
    return query("MATCH (u:User) RETURN u.name AS name ORDER BY u.name")

def get_songs() -> list[dict[str, Any]]:
    return query("MATCH (s:Song) RETURN s.title AS title ORDER BY s.title")

def get_dashboard_metrics() -> dict[str, int]:
    rows = query(
        """
        MATCH (u:User) WITH count(u) AS users
        MATCH (s:Song) WITH users, count(s) AS songs
        MATCH ()-[r:LIKES]->()
        RETURN users, songs, count(r) AS likes
        """
    )
    return rows[0] if rows else {"users": 0, "songs": 0, "likes": 0}

def get_profile(user_name: str) -> dict[str, Any] | None:
    rows = query(
        """
        MATCH (u:User {name:$user_name})
        OPTIONAL MATCH (u)-[:LIKES]->(s:Song)
        RETURN u.name AS name, collect(DISTINCT s.title) AS liked_songs
        """,
        {"user_name": user_name},
    )
    return rows[0] if rows else None

def recommend_songs(user_name: str, limit: int = 8) -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:User {name:$user_name})-[:LIKES]->(s:Song)<-[:LIKES]-(other:User)-[:LIKES]->(rec_s:Song)
        WHERE NOT (u)-[:LIKES]->(rec_s)
        WITH rec_s, count(other) AS score, collect(DISTINCT other.name) AS similar_users
        RETURN rec_s.title AS title, score, similar_users
        ORDER BY score DESC, rec_s.title
        LIMIT $limit
        """,
        {"user_name": user_name, "limit": int(limit)},
    )

def search_songs(keyword: str = "") -> list[dict[str, Any]]:
    return query(
        """
        MATCH (s:Song)
        WHERE $keyword = '' OR toLower(s.title) CONTAINS toLower($keyword)
        OPTIONAL MATCH (u:User)-[:LIKES]->(s)
        RETURN s.title AS title, count(u) AS total_likes
        ORDER BY total_likes DESC, s.title
        """,
        {"keyword": keyword.strip()},
    )

def graph_neighborhood(user_name: str, limit: int = 40) -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:User {name:$user_name})
        OPTIONAL MATCH p=(u)-[:LIKES*1..3]-(x)
        WITH u, collect(p)[0..$limit] AS paths
        UNWIND paths AS p
        UNWIND relationships(p) AS r
        WITH DISTINCT startNode(r) AS s, r, endNode(r) AS t
        RETURN elementId(s) AS source_id, labels(s)[0] AS source_label,
               coalesce(s.name, s.title) AS source_name,
               type(r) AS relationship,
               elementId(t) AS target_id, labels(t)[0] AS target_label,
               coalesce(t.name, t.title) AS target_name
        LIMIT $limit
        """,
        {"user_name": user_name, "limit": int(limit)},
    )

# --- CREATE ---
def add_user(name: str) -> None:
    query("MERGE (u:User {name: $name})", {"name": name}, write=True)

def add_song(title: str) -> None:
    query("MERGE (s:Song {title: $title})", {"title": title}, write=True)

def record_like(user_name: str, song_title: str) -> None:
    query(
        """
        MATCH (u:User {name:$user_name}), (s:Song {title:$song_title})
        MERGE (u)-[:LIKES]->(s)
        """,
        {"user_name": user_name, "song_title": song_title},
        write=True,
    )

# --- UPDATE (Admin) ---
def update_user(old_name: str, new_name: str) -> None:
    query("MATCH (u:User {name: $old_name}) SET u.name = $new_name", {"old_name": old_name, "new_name": new_name}, write=True)

def update_song(old_title: str, new_title: str) -> None:
    query("MATCH (s:Song {title: $old_title}) SET s.title = $new_title", {"old_title": old_title, "new_title": new_title}, write=True)

# --- DELETE (Admin) ---
def delete_user(name: str) -> None:
    query("MATCH (u:User {name: $name}) DETACH DELETE u", {"name": name}, write=True)

def delete_song(title: str) -> None:
    query("MATCH (s:Song {title: $title}) DETACH DELETE s", {"title": title}, write=True)

def remove_like(user_name: str, song_title: str) -> None:
    query(
        """
        MATCH (u:User {name:$user_name})-[r:LIKES]->(s:Song {title:$song_title})
        DELETE r
        """,
        {"user_name": user_name, "song_title": song_title}, write=True
    )