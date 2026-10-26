"""Main Blueprint - Public Pages"""

from flask import Blueprint

bp = Blueprint('main', __name__)

from app.main import routes  # noqa: F401
from app.main import cart  # noqa: F401
from app.main import checkout  # noqa: F401
from app.main import orders  # noqa: F401
from app.main import reviews  # noqa: F401
from app.main import profile  # noqa: F401