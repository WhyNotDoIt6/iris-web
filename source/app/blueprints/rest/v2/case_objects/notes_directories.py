#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.access_controls import ac_api_return_access_denied
from app.business.errors import ObjectNotFoundError
from app.business.errors import BusinessProcessingError
from app.schema.marshables import CaseNoteDirectorySchema
from app.business.notes_directories import notes_directories_create
from app.business.notes_directories import notes_directories_get
from app.business.notes_directories import notes_directories_update
from app.business.notes_directories import notes_directories_delete
from app.datamgmt.case.case_notes_db import get_directories_with_note_count
from app.business.cases import cases_exists
from app.datamgmt.case.case_db import get_case
from app.iris_engine.access_control.utils import ac_fast_check_current_user_has_case_access
from app.models.authorization import CaseAccessLevel


case_notes_directories_blueprint = Blueprint('case_notes_directories_rest_v2',
                                        __name__,
                                        url_prefix='/<int:case_identifier>/notes-directories')


def _load(request_data, **kwargs):
    notes_directories_schema = CaseNoteDirectorySchema()
    return notes_directories_schema.load(request_data, **kwargs)


@case_notes_directories_blueprint.post('')
@ac_api_requires()
def create(case_identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(case_identifier)

    request_data = request.get_json()
    request_data.pop('id', None)
    request_data['case_id'] = case_identifier

    notes_directories_schema = CaseNoteDirectorySchema()

    try:
        if request_data.get('parent_id') is not None:
            notes_directories_schema.verify_parent_id(request_data['parent_id'], case_id=case_identifier)
        directory = _load(request_data)

        notes_directories_create(directory)
        return response_api_created(notes_directories_schema.dump(directory))

    except ValidationError as e:
        return response_api_error('Data error', data=e.normalized_messages())


@case_notes_directories_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get(case_identifier, identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier,
                                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(case_identifier)

    notes_directories_schema = CaseNoteDirectorySchema()
    try:
        note_directory = get_note_directory_in_case(identifier, case_identifier)
        return response_api_success(notes_directories_schema.dump(note_directory))

    except ObjectNotFoundError:
        return response_api_not_found()

    except BusinessProcessingError as e:
        return response_api_error(e.get_message())


@case_notes_directories_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update(case_identifier, identifier):
    if not cases_exists(case_identifier):
        return response_api_not_found()
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(case_identifier)

    notes_directories_schema = CaseNoteDirectorySchema()
    try:
        directory = get_note_directory_in_case(identifier, case_identifier)

        request_data = request.get_json()

        if request_data.get('parent_id') is not None:
            notes_directories_schema.verify_parent_id(request_data['parent_id'], case_id=case_identifier, current_id=identifier)

        new_directory = _load(request_data, instance=directory, partial=True)
        notes_directories_update(new_directory)
        return response_api_success(notes_directories_schema.dump(directory))

    except ValidationError as e:
        return response_api_error('Data error', data=e.normalized_messages())

    except ObjectNotFoundError:
        return response_api_not_found()

    except BusinessProcessingError as e:
        return response_api_error('Data error', data=e.get_data())


@case_notes_directories_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete(case_identifier, identifier):
    if not ac_fast_check_current_user_has_case_access(case_identifier, [CaseAccessLevel.full_access]):
        return ac_api_return_access_denied(case_identifier)

    try:
        directory = get_note_directory_in_case(identifier, case_identifier)
        notes_directories_delete(directory)
        return response_api_deleted()

    except ObjectNotFoundError:
        return response_api_not_found()


@case_notes_directories_blueprint.get('')
@ac_api_requires()
def get_filter(case_identifier):
    if not get_case(case_identifier):
        return response_api_error("Invalid case ID")

    directories = get_directories_with_note_count(case_identifier)
    return response_api_success(directories)


def get_note_directory_in_case(identifier, case_identifier):
    directory = notes_directories_get(identifier)
    if directory.case_id != case_identifier:
        raise ObjectNotFoundError()
    return directory
