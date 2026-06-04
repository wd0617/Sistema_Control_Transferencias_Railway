release: python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
web: gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"
