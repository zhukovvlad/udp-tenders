from crud.compensation_corridors import (
    delete_corridor,
    get_corridor_map,
    get_corridors,
    set_corridor,
)
from tests.factories import MaterialClassFactory, ProjectFactory


def test_set_corridor_creates_then_get_map(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")

    set_corridor(db_session, project.id, mc.id, 5.0)

    assert get_corridor_map(db_session, project.id) == {mc.id: 5.0}


def test_set_corridor_is_idempotent_upsert(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")

    set_corridor(db_session, project.id, mc.id, 5.0)
    set_corridor(db_session, project.id, mc.id, 7.0)  # overwrite, no duplicate row

    rows = get_corridors(db_session, project.id)
    assert len(rows) == 1
    assert rows[0].corridor_pct == 7.0


def test_delete_corridor_idempotent(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    set_corridor(db_session, project.id, mc.id, 5.0)

    assert delete_corridor(db_session, project.id, mc.id) is True
    assert delete_corridor(db_session, project.id, mc.id) is False  # already gone
    assert get_corridor_map(db_session, project.id) == {}


def test_zero_corridor_is_stored(db_session, factories):
    project = ProjectFactory.create()
    mc = MaterialClassFactory.create(material_type="concrete", name="В25")
    set_corridor(db_session, project.id, mc.id, 0.0)
    assert get_corridor_map(db_session, project.id) == {mc.id: 0.0}
