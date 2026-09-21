import asyncio
import pytest
from app.services.agent_questions import specialists,respond
from app.api.routes import agents
from test_asset_ownership import assets,acting,ALICE,BOB
from app.services import analysis_records

def test_questions_route_and_do_not_repeat():
 evidence={"dataset_id":"d","rows":10,"sha256":"abc","curves":{"density_gcc":{"valid":9,"excluded":1,"median":2.4,"minimum":2.1,"maximum":2.7}},"issues":[]}
 assert specialists("What is the RHOB range?")==["petrophysicist"]
 assert specialists("Are there missing units?")==["qa"]
 a=respond("petrophysicist","What is the RHOB range?",evidence)
 b=respond("qa","Which curves are missing?",evidence)
 assert a[0]!=b[0] and "2.4" in a[0][0] and "1 missing" in b[0][1]
 assert "outside" in respond("drilling","What is the RHOB range?",evidence)[0][0]
 assert "do not establish" in respond("petrophysicist","What is permeability?",evidence)[0][-1]

def test_saved_analysis_agent_access(assets):
 a,b,legacy,client,user=assets
 client.app.include_router(agents.router,prefix="/agents")
 with acting(ALICE):saved=analysis_records.save({"porosity":.21,"provenance":{"well_id":"A","source_row":1}})
 response=client.post("/agents/petrophysicist/run",json={"analysis_id":saved["analysis_id"],"objective":"What is porosity?"})
 assert response.status_code==200 and any("0.21" in x for x in response.json()["findings"])
 user["value"]=BOB
 assert client.post("/agents/petrophysicist/run",json={"analysis_id":saved["analysis_id"],"objective":"What is porosity?"}).status_code==404
