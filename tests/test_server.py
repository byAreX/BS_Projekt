import http.client
import json
import sys
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

    def test_touch_home_stops_managed_carplay_process(self):
        with patch.object(server, 'PREVIEW', False), patch.dict(server.PROCESSES, {}, clear=True), \
                patch('subprocess.Popen') as popen:
            carplay = popen.return_value
            carplay.poll.return_value = None
            server.PROCESSES['carplay'] = carplay
            self.assertEqual(self.request('/api/carplay/stop', {}, self.auth())[0], 200)
            carplay.terminate.assert_called_once()
            carplay.wait.assert_called_once_with(timeout=5)


if __name__ == '__main__':
    unittest.main()
