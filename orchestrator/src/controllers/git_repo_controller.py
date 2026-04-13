from flask import Blueprint, request

from src.models.orchestrator.GitRepo import GitRepo
from src.persistence.GitRepoStorage import GitRepoStorage

git_repo_blueprint = Blueprint('git_repos', __name__)

_storage = GitRepoStorage()


@git_repo_blueprint.route('/list', methods=['GET'])
def list_repos():
    try:
        repos = _storage.get_repos()
        return [r.to_dict() for r in repos]
    except Exception as e:
        return {
            'message': f"Something went wrong: {e}",
            'status': 500,
            'error': str(e),
        }, 500


@git_repo_blueprint.route('/get', methods=['GET'])
def get_repo():
    try:
        raw_id = request.args.get('repo_id')
        if not raw_id:
            return {'message': 'Missing required query parameter: repo_id', 'status': 400}, 400

        repo = _storage.get_repo(int(raw_id))
        if repo is None:
            return {'message': 'Repo not found', 'status': 404}, 404

        return repo.to_dict()
    except ValueError:
        return {'message': 'Invalid repo_id', 'status': 400}, 400
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@git_repo_blueprint.route('/', methods=['POST'])
def upsert_repo():
    try:
        data = request.get_json(silent=True)
        if not data:
            return {'message': 'Missing or invalid JSON body', 'status': 400}, 400

        repo = GitRepo.from_dict(data)

        if not repo.name or not repo.url:
            return {'message': 'name and url are required', 'status': 400}, 400

        if repo.id and repo.id > 0:
            _storage.update_repo(repo)
            updated = _storage.get_repo(repo.id)
            if updated is None:
                return {'message': 'Repo not found after update', 'status': 404}, 404
            return updated.to_dict()
        else:
            new_id = _storage.create_repo(repo)
            created = _storage.get_repo(new_id)
            if created is None:
                return {'message': 'Repo not found after create', 'status': 500}, 500
            return created.to_dict()

    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500


@git_repo_blueprint.route('/<int:repo_id>', methods=['DELETE'])
def delete_repo(repo_id: int):
    try:
        existing = _storage.get_repo(repo_id)
        if existing is None:
            return {'message': 'Repo not found', 'status': 404}, 404

        _storage.delete_repo(repo_id)
        return {'message': 'Repo deleted', 'status': 200}
    except Exception as e:
        return {'message': f"Something went wrong: {e}", 'status': 500, 'error': str(e)}, 500
