"""Test config entries API."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant import auth
from homeassistant.setup import async_setup_component
from homeassistant.components.config import (
    auth_provider_homeassistant as auth_ha)

from tests.common import MockUser, CLIENT_ID


@pytest.fixture(autouse=True)
def auth_active(hass):
    """Mock that auth is active."""
    with patch('homeassistant.auth.AuthManager.active',
               PropertyMock(return_value=True)):
        yield


@pytest.fixture(autouse=True)
def setup_config(hass, aiohttp_client):
    """Fixture that sets up the auth provider homeassistant module."""
    hass.loop.run_until_complete(async_setup_component(
        hass, 'websocket_api', {}))
    hass.loop.run_until_complete(auth_ha.async_setup(hass))


async def test_get_users_requires_owner(hass, hass_ws_client,
                                        hass_access_token):
    """Test get users requires auth."""
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = False

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_LIST,
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_get_users(hass, hass_ws_client):
    """Test get users."""
    owner = MockUser(
        id='abc',
        name='Test Owner',
        is_owner=True,
    ).add_to_hass(hass)

    owner.credentials.append(auth.Credentials(
        auth_provider_type='homeassistant',
        auth_provider_id=None,
        data={},
    ))

    system = MockUser(
        id='efg',
        name='Test Hass.io',
        system_generated=True
    ).add_to_hass(hass)

    inactive = MockUser(
        id='hij',
        name='Inactive User',
        is_active=False,
    ).add_to_hass(hass)

    refresh_token = await hass.auth.async_create_refresh_token(
        owner, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_LIST,
    })

    result = await client.receive_json()
    assert result['success'], result
    data = result['result']
    assert len(data) == 3
    assert data[0] == {
        'id': owner.id,
        'name': 'Test Owner',
        'is_owner': True,
        'is_active': True,
        'system_generated': False,
        'credentials': [{'type': 'homeassistant'}]
    }
    assert data[1] == {
        'id': system.id,
        'name': 'Test Hass.io',
        'is_owner': False,
        'is_active': True,
        'system_generated': True,
        'credentials': [],
    }
    assert data[2] == {
        'id': inactive.id,
        'name': 'Inactive User',
        'is_owner': False,
        'is_active': False,
        'system_generated': False,
        'credentials': [],
    }
