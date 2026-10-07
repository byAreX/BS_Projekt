import http.client
import json
import os
import stat
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.port = cls.http.server_port
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def request(self, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        connection.request('GET' if body is None else 'POST', path,
                           None if body is None else json.dumps(body), headers or {})
        response = connection.getresponse()
        code, data = response.status, response.read()
        connection.close()
        return code, json.loads(data)

    def auth(self):
        return {'Origin':f'http://127.0.0.1:{self.port}', 'X-DriveSphere-Token':server.TOKEN,
                'Content-Type':'application/json'}

    def test_preview_does_not_query_hardware(self):
        with patch.object(server, 'PREVIEW', True), patch.object(server, 'command') as command:
            code, state = self.request('/api/status')
            self.assertEqual(code, 200)
            self.assertTrue(state['preview'])
            self.assertEqual(state['bluetooth']['devices'], [])
            command.assert_not_called()
            self.assertEqual(self.request('/api/carplay', {}, self.auth())[0], 409)

    def test_write_requires_local_origin_and_token(self):
        self.assertEqual(self.request('/api/volume', {'value':30})[0], 403)
        headers = self.auth()
        headers['Origin'] = 'https://example.com'
        self.assertEqual(self.request('/api/volume', {'value':30}, headers)[0], 403)
        self.assertEqual(self.request('/api/status', headers={'Host':'attacker.test'})[0], 403)

    def test_volume_validation_and_argv(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'command') as command:
            for bad in [-1, 101, True, '50; touch /tmp/test', None]:
                self.assertEqual(self.request('/api/volume', {'value':bad}, self.auth())[0], 400)
            command.assert_not_called()
            self.assertEqual(self.request('/api/volume', {'value':35}, self.auth())[0], 200)
            self.assertEqual(command.call_args_list[0].args[0], ['wpctl','set-volume','@DEFAULT_AUDIO_SINK@','35%'])

    def test_bluetooth_rejects_unpaired_and_invalid_addresses(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'command', return_value='') as command:
            self.assertEqual(self.request('/api/bluetooth', {'address':'bad; reboot','connect':True}, self.auth())[0], 400)
            command.assert_not_called()
            self.assertEqual(self.request('/api/bluetooth', {'address':'AA:BB:CC:DD:EE:FF','connect':True}, self.auth())[0], 400)
            self.assertEqual(command.call_count, 1)

    def test_bluetooth_only_connects_selected_paired_device(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'command', return_value='Device AA:BB:CC:DD:EE:FF Cardo') as command:
            self.assertEqual(self.request('/api/bluetooth', {'address':'AA:BB:CC:DD:EE:FF','connect':True}, self.auth())[0], 200)
            self.assertEqual(command.call_args.args[0], ['bluetoothctl','connect','AA:BB:CC:DD:EE:FF'])

    def test_command_reports_bluez_failure_even_on_zero_exit(self):
        with patch('subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'Failed to connect: org.bluez.Error.Failed'
            run.return_value.stderr = ''
            with self.assertRaises(ValueError):
                server.command(['bluetoothctl','connect','AA:BB:CC:DD:EE:FF'])

    def test_duplicate_native_launch_is_prevented(self):
        with patch.dict(server.PROCESSES, {}, clear=True), patch('subprocess.Popen') as popen:
            popen.return_value.poll.return_value = None
            server.launch('carplay', ['/test/livi'])
            with self.assertRaises(ValueError):
                server.launch('carplay', ['/test/livi'])
            popen.assert_called_once()

    def test_carplay_requires_touch_home_before_launch(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'CONFIG', {'carplay_command':['/test/livi']}), \
                patch.object(server, 'touch_home_available', return_value=False), patch('subprocess.Popen') as popen:
            self.assertEqual(self.request('/api/carplay', {}, self.auth())[0], 400)
            popen.assert_not_called()

    def test_stop_ends_managed_carplay_and_livi_compositor(self):
        with patch.object(server, 'PREVIEW', False), patch.dict(server.PROCESSES, {}, clear=True), \
                patch.object(server, 'carplay_window_action', side_effect=[True, False]), \
                patch('subprocess.run') as run, patch('subprocess.Popen') as popen:
            carplay = popen.return_value
            carplay.poll.return_value = None
            server.PROCESSES['carplay'] = carplay
            self.assertEqual(self.request('/api/carplay/stop', {}, self.auth())[0], 200)
            carplay.terminate.assert_called_once()
            carplay.wait.assert_called_once_with(timeout=5)
            self.assertEqual(run.call_args.args[0][-2:], ['-x', 'livi-compositor'])

    def test_running_carplay_is_brought_to_front_not_restarted(self):
        actions = []
        def window(action, *matches):
            actions.append(action)
            return True
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'CONFIG', {'carplay_command':['/test/livi']}), \
                patch.object(server, 'touch_home_available', return_value=True), \
                patch.object(server, 'start_touch_home'), patch.object(server, 'carplay_window_action', side_effect=window), \
                patch('subprocess.Popen') as popen:
            code, result = self.request('/api/carplay', {}, self.auth())
            self.assertEqual(code, 200)
            self.assertEqual(result['message'], 'CarPlay ist wieder im Vordergrund.')
            self.assertEqual(actions, ['find', 'focus'])
            popen.assert_not_called()

    def test_hide_minimizes_carplay_window(self):
        with patch.object(server, 'PREVIEW', False), \
                patch.object(server, 'carplay_window_action', return_value=True) as window:
            self.assertEqual(self.request('/api/carplay/hide', {}, self.auth())[0], 200)
            window.assert_called_once_with('minimize')
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'carplay_window_action', return_value=False):
            self.assertEqual(self.request('/api/carplay/hide', {}, self.auth())[0], 400)

    def test_invalid_carplay_window_match_is_ignored(self):
        with patch.object(server, 'CONFIG', {'carplay_window':'app_id:x; reboot'}):
            self.assertEqual(server.carplay_window(), '')
            self.assertFalse(server.carplay_window_action('find'))

    def test_pairing_endpoints_validate_input(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'command', return_value='') as command, \
                patch.object(server, 'start_pairing') as start:
            self.assertEqual(self.request('/api/bluetooth/pair', {'address':'x; reboot'}, self.auth())[0], 400)
            self.assertEqual(self.request('/api/bluetooth/remove', {'address':'AA:BB:CC:DD:EE:FF'}, self.auth())[0], 400)
            start.assert_not_called()
            self.assertNotIn(['bluetoothctl','remove','AA:BB:CC:DD:EE:FF'], [c.args[0] for c in command.call_args_list])
            with patch.object(server, 'PAIRING', None):
                self.assertEqual(self.request('/api/bluetooth/answer', {'pin':'0000'}, self.auth())[0], 400)

    def test_remove_only_paired_device(self):
        with patch.object(server, 'PREVIEW', False), patch.object(server, 'command', return_value='Device AA:BB:CC:DD:EE:FF Cardo') as command:
            self.assertEqual(self.request('/api/bluetooth/remove', {'address':'AA:BB:CC:DD:EE:FF'}, self.auth())[0], 200)
            self.assertEqual(command.call_args.args[0], ['bluetoothctl','remove','AA:BB:CC:DD:EE:FF'])


FAKE_BLUETOOTHCTL = r"""#!/usr/bin/env python3
import os
mode = os.environ['FAKE_BT_MODE']
print('[0;94mAgent registered[0m', flush=True)
while True:
    try:
        command = input('[bluetooth]# ').split()
    except EOFError:
        break
    if command == ['scan', 'on']:
        print('[[0;92mNEW[0m] Device AA:BB:CC:DD:EE:FF Cardo', flush=True)
    elif command[:1] == ['pair']:
        if mode == 'confirm':
            ok = input('[0;91m[agent][0m Confirm passkey 123456 (yes/no): ') == 'yes'
        elif mode == 'pin':
            ok = input('[0;91m[agent][0m Enter PIN code: ') == '0000'
        else:
            ok = False
        print('Pairing successful' if ok else 'Failed to pair: org.bluez.Error.AuthenticationFailed', flush=True)
    elif command[:1] == ['trust']:
        print('Changing AA:BB:CC:DD:EE:FF trust succeeded', flush=True)
    elif command[:1] == ['connect']:
        print('Connection successful', flush=True)
    elif command == ['quit']:
        break
"""


class PairingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        fake = Path(folder.name) / 'bluetoothctl'
        fake.write_text(FAKE_BLUETOOTHCTL)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        patcher = patch.object(server, 'BLUETOOTHCTL', str(fake))
        patcher.start()
        self.addCleanup(patcher.stop)

    def pair(self, mode):
        with patch.dict(os.environ, {'FAKE_BT_MODE':mode}):
            return server.Pairing('AA:BB:CC:DD:EE:FF', 'Cardo')

    def wait_for(self, session, steps):
        deadline = time.monotonic() + 10
        while session.step not in steps and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertIn(session.step, steps, session.message)

    def test_passkey_is_shown_and_confirmed(self):
        session = self.pair('confirm')
        self.wait_for(session, {'confirm'})
        self.assertEqual(session.passkey, '123456')
        session.answer()
        self.wait_for(session, {'done'})
        self.assertEqual(session.message, 'Verbunden.')

    def test_pin_is_entered(self):
        session = self.pair('pin')
        self.wait_for(session, {'pin'})
        with self.assertRaises(ValueError):
            session.answer('12a4')
        session.answer('0000')
        self.wait_for(session, {'done'})

    def test_rejected_pairing_reports_failure(self):
        session = self.pair('fail')
        self.wait_for(session, {'failed'})
        self.assertIn('abgelehnt', session.message)

    def test_cancel_stops_session(self):
        session = self.pair('confirm')
        self.wait_for(session, {'confirm'})
        session.cancel()
        self.wait_for(session, {'failed'})
        self.assertEqual(session.message, 'Kopplung abgebrochen.')


if __name__ == '__main__':
    unittest.main()
