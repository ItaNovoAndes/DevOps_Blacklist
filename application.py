from app import create_app

# Elastic Beanstalk (gunicorn) busca el objeto `application` en este módulo.
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000, debug=True)
