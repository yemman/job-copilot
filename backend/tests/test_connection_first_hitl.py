from app.services.outreach import normalize_company_name


def test_linkedin_csv_import_and_company_matching(client):
    csv_bytes = (
        "Notes:\n"
        "\"When exporting, you can import your contacts.\"\n"
        "\n"
        "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
        "Maya,Cohen,https://linkedin.com/in/maya,maya@stripe.com,\"Stripe, Inc.\",Staff Engineer,01 Oct 2024\n"
        "Alex,Ng,https://linkedin.com/in/alex,,Linear Labs,Product Engineer,12 Nov 2024\n"
    ).encode("utf-8")

    assert normalize_company_name("Stripe, Inc.") == "stripe"

    imp = client.post(
        "/api/contacts/import-linkedin-csv",
        files={"file": ("Connections.csv", csv_bytes, "text/csv")},
    )
    assert imp.status_code == 200
    assert imp.json()["inserted"] == 2


def test_connection_first_hitl_workflow(client):
    # Seed demo data & generate digest
    client.post("/api/demo/seed")
    gen = client.post("/api/digests/generate", json={"force": True, "sync_sources": False})
    assert gen.status_code == 200
    items = gen.json()["digest"]["items"]
    assert 3 <= len(items) <= 5

    # Approve first digest item -> enters connection_search
    first_item = items[0]
    dec = client.post(f"/api/digests/items/{first_item['id']}/decide", json={"decision": "approved"})
    assert dec.status_code == 200
    app_id = dec.json()["application_id"]
    assert app_id is not None

    app_data = client.get(f"/api/applications/{app_id}").json()
    assert app_data["stage"] == "connection_search"

    # Connection lookup returns linkedin_search_url
    conn_res = client.get(f"/api/applications/{app_id}/connections")
    assert conn_res.status_code == 200
    assert "linkedin.com/search/results/people" in conn_res.json()["linkedin_search_url"]

    # Direct transition to 'applied' without outreach or override reason MUST fail (400)
    blocked = client.post(f"/api/applications/{app_id}/transition", json={"stage": "applied"})
    assert blocked.status_code == 400
    assert "Connection-first gate" in blocked.json()["detail"]

    # Draft LinkedIn connection note -> <= 300 chars, starts in 'draft'
    draft_res = client.post(
        f"/api/applications/{app_id}/outreach/draft",
        json={"contact_name": "Maya Cohen", "channel": "linkedin_connect_note"},
    )
    assert draft_res.status_code == 201
    msg = draft_res.json()
    assert msg["status"] == "draft"
    assert len(msg["body"]) <= 300

    # Cannot mark sent before approving
    early_send = client.post(f"/api/outreach/{msg['id']}/mark-sent")
    assert early_send.status_code == 400

    # Approve -> Mark Sent -> now ready_to_apply / applied succeeds
    approved = client.post(f"/api/outreach/{msg['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    sent = client.post(f"/api/outreach/{msg['id']}/mark-sent")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["follow_up_at"] is not None

    # Now transitioning to applied works cleanly without override
    applied = client.post(f"/api/applications/{app_id}/transition", json={"stage": "applied"})
    assert applied.status_code == 200
    assert applied.json()["stage"] == "applied"
    assert applied.json()["applied_at"] is not None


def test_connection_override_allows_direct_apply(client):
    client.post("/api/demo/seed")
    gen = client.post("/api/digests/generate", json={"force": True, "sync_sources": False})
    item = gen.json()["digest"]["items"][0]
    app_id = client.post(
        f"/api/digests/items/{item['id']}/decide", json={"decision": "approved"}
    ).json()["application_id"]

    override = client.post(
        f"/api/applications/{app_id}/transition",
        json={"stage": "applied", "connection_override_reason": "No connections found at company"},
    )
    assert override.status_code == 200
    assert override.json()["stage"] == "applied"
    assert override.json()["connection_override_reason"] == "No connections found at company"
