import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import httpx
from app import Application, handler_for
from hunter import Store, collect, load_companies, refresh
from main import is_target_role


def listing(id='1', title='Propulsion Engineering Intern'):
    return dict(id=id, title=title, location='Seattle', url='https://example.com/job')


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'jobs.sqlite3')

    def tearDown(self):
        self.temp.cleanup()

    def test_refresh_preserves_notes_stage_and_first_seen(self):
        self.assertEqual(self.store.record('Rocket', [listing()]), 1)
        original = self.store.snapshot()['jobs'][0]
        self.store.update(original['id'], 'applied', 'Follow up Friday')
        self.assertEqual(self.store.record('Rocket', [listing(title='Flight Engineering Intern')]), 0)
        job = self.store.snapshot()['jobs'][0]
        self.assertEqual((job['status'], job['notes'], job['first_seen']), ('applied', 'Follow up Friday', original['first_seen']))
        self.assertEqual(job['title'], 'Flight Engineering Intern')
        self.assertEqual(Store(self.store.path).snapshot()['jobs'], [job])

    def test_failures_preserve_open_jobs_success_closes_and_reopens(self):
        self.store.record('Rocket', [listing()])
        self.store.record('Rocket', error='HTTP 429')
        self.assertEqual(self.store.snapshot()['jobs'][0]['active'], 1)
        self.store.record('Rocket', [])
        self.assertEqual(self.store.snapshot()['jobs'][0]['active'], 0)
        self.store.record('Rocket', [listing()])
        self.assertEqual(self.store.snapshot()['jobs'][0]['active'], 1)

    def test_company_ids_do_not_collide(self):
        self.store.record('A', [listing(), listing()])
        self.store.record('B', [listing()])
        self.assertEqual(len(self.store.snapshot()['jobs']), 2)

    def test_invalid_stage_rejected(self):
        self.store.record('A', [listing()])
        with self.assertRaises(ValueError):
            self.store.update(self.store.snapshot()['jobs'][0]['id'], 'garbage', '')


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_greenhouse_http_failure_is_not_empty_success(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as client:
            with self.assertRaises(httpx.HTTPStatusError):
                await collect(client, dict(provider='greenhouse', board='test'))

    async def test_lever_paginates_and_requests_json(self):
        calls = []
        def respond(request):
            calls.append(request)
            self.assertEqual(request.url.params['mode'], 'json')
            skip = int(request.url.params['skip'])
            return httpx.Response(200, json=[dict(id=str(i), text='Engineering Intern', hostedUrl='https://example.com', categories={}) for i in range(skip, min(skip + 100, 105))])
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            jobs = await collect(client, dict(provider='lever', board='test'))
        self.assertEqual(len(jobs), 105)
        self.assertEqual(len(calls), 2)

    async def test_workday_incomplete_pages_fail(self):
        def respond(request):
            offset = json.loads(request.content)['offset']
            return httpx.Response(200, json={'total': 2, 'jobPostings': [] if offset else [{'externalPath':'/job/1','title':'Engineering Intern'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with self.assertRaises(ValueError):
                await collect(client, dict(provider='workday', host='example.com',tenant='a',site='b'))

    async def test_workday_uses_first_page_total(self):
        def respond(request):
            offset = json.loads(request.content)['offset']
            return httpx.Response(200, json={'total': 3 if offset == 0 else 0,
                'jobPostings': [{'externalPath':f'/job/{offset}', 'title':'Engineering Intern'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            jobs = await collect(client, dict(provider='workday', host='example.com',tenant='a',site='b'))
        self.assertEqual(len(jobs), 3)

    async def test_malformed_board_is_not_empty_success(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as client:
            with self.assertRaises(KeyError):
                await collect(client, dict(provider='greenhouse',board='test'))

    async def test_ashby_feed(self):
        payload = {'jobs': [{'title':'Flight Software Intern', 'location':'Denver',
                             'jobUrl':'https://jobs.ashbyhq.com/test/abc'}]}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as client:
            jobs = await collect(client, dict(provider='ashby', board='test'))
        self.assertEqual(jobs, [{'id':'https://jobs.ashbyhq.com/test/abc', 'title':'Flight Software Intern',
                                 'location':'Denver', 'url':'https://jobs.ashbyhq.com/test/abc'}])

    async def test_smartrecruiters_paginates(self):
        calls = []
        def respond(request):
            calls.append(request)
            offset = int(request.url.params['offset'])
            content = [{'id':str(i), 'name':'Aerospace Intern',
                        'location':{'city':'Dallas','region':'Texas','country':'US'},
                        'ref':f'https://jobs.smartrecruiters.com/test/{i}'} for i in range(offset, min(offset + 100, 101))]
            return httpx.Response(200, json={'content':content, 'totalFound':101})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            jobs = await collect(client, dict(provider='smartrecruiters', board='test'))
        self.assertEqual(len(jobs), 101)
        self.assertEqual(len(calls), 2)

    async def test_manual_company_is_not_requested(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: self.fail('network called'))) as client:
            self.assertEqual(await collect(client, dict(provider='manual')), [])

    async def test_failed_alert_retries_on_next_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'jobs.sqlite3')
            store.record('A', [listing()])
            real_client = httpx.AsyncClient
            codes = iter([500, 204])
            factory = lambda **kwargs: real_client(transport=httpx.MockTransport(lambda r: httpx.Response(next(codes))))
            with patch.dict('os.environ', {'DISCORD_WEBHOOK_URL':'https://example.com/webhook'}), patch('hunter.httpx.AsyncClient', factory):
                result = await refresh(store, [])
                self.assertIsNotNone(result['notification_error'])
                self.assertEqual(store.snapshot()['jobs'][0]['notified'], 0)
                await refresh(store, [])
                self.assertEqual(store.snapshot()['jobs'][0]['notified'], 1)

    async def test_refresh_marks_manual_sources_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'jobs.sqlite3')
            real_client = httpx.AsyncClient
            factory = lambda **kwargs: real_client(transport=httpx.MockTransport(lambda r: self.fail('network called')))
            with patch('hunter.httpx.AsyncClient', factory):
                await refresh(store, [{'name':'Small Space Shop', 'provider':'manual',
                                       'careers_url':'https://example.com/careers'}])
            source = store.snapshot()['sources'][0]
            self.assertEqual((source['company'], source['state']), ('Small Space Shop', 'manual'))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(Store(Path(self.temp.name) / 'jobs.sqlite3'))
        self.app.store.record('Rocket', [listing()])
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = httpx.Client(base_url=f'http://127.0.0.1:{self.server.server_port}')

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_state_update_export_and_host_protection(self):
        state = self.client.get('/api/state').json()
        job = state['jobs'][0]
        path = '/api/jobs/' + job['id']
        self.assertEqual(self.client.post(path, json={'status':'saved'}).status_code, 403)
        response = self.client.post(path, json={'status':'applied','notes':'=DANGEROUS()'}, headers={'X-App-Token':state['token']})
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=DANGEROUS()", self.client.get('/api/export').text)
        self.assertEqual(self.client.get('/api/state', headers={'Host':'evil.example'}).status_code, 403)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/../hunter.py').status_code, 404)

    def test_double_refresh_is_rejected(self):
        self.app.state['running'] = True
        self.assertFalse(self.app.start_refresh())


class MatchingTests(unittest.TestCase):
    def test_word_boundaries_and_coop_variants(self):
        self.assertFalse(is_target_role('Contest Marketing Intern'))
        self.assertTrue(is_target_role('Mechanical Engineering Co op'))
        self.assertTrue(is_target_role('Avionics Internship'))

    def test_catalog_is_broad_unique_and_contains_requested_companies(self):
        companies = load_companies()
        names = {company['name'] for company in companies}
        self.assertGreaterEqual(len(companies), 300)
        self.assertEqual(len(names), len(companies))
        for name in ('CesiumAstro', 'Zipline', 'AeroVironment', 'Odyssey Space Research',
                     'CACI International', 'K2 Space', 'Katalyst Space Technologies',
                     'Spirit AeroSystems', 'Whisper Aero', 'United Launch Alliance',
                     'Garmin', 'Moog', 'L3Harris Technologies'):
            self.assertIn(name, names)


if __name__ == '__main__':
    unittest.main()
