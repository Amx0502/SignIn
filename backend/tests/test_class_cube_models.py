from app.class_cube_models import task_view


def test_task_view_returns_saved_password_to_authorized_editor():
    view = task_view(
        {
            "id": 3,
            "owner_user_id": 1,
            "account_id": 4,
            "course_id": 7,
            "name": "密码签到",
            "password": "2468",
        }
    )

    assert view["password"] == "2468"
    assert view["has_password"] is True
