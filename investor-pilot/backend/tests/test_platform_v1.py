from app.platform_v1.database import initialise
from app.platform_v1.experiments import create_experiment
from app.platform_v1.schemas import ExperimentCreate


def test_database_initialises():
    initialise()


def test_experiment_records():
    experiment = create_experiment(
        ExperimentCreate(name="Test experiment", task="fluid_type_classification", algorithm="random_forest", validation_strategy="grouped_by_well"),
        "test-user",
    )
    assert experiment.experiment_id.startswith("exp-")


def test_platform_route_imports():
    from app.api.routes.platform import router
    assert router.prefix == "/platform"