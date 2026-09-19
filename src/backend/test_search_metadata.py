import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import app as backend
from search_validation import validate_read_only,unsupported_shot_style

class ValidationTests(unittest.TestCase):
    def test_command_words_inside_literals_comments_and_iris_are_data(self):
        queries = [
            'SELECT ?x WHERE { ?x ?p "players WITH assists" . }',
            "SELECT ?x WHERE { ?x ?p 'SERVICE WITH INSERT' . }",
            'PREFIX b: <https://example.com/WITH#> SELECT ?x WHERE { ?x b:label "WITH" . } # DELETE',
            'SELECT ?with WHERE { ?with <https://example.com/SERVICE> """WITH\nDELETE""" . }',
            "SELECT ?x WHERE { ?x ?p '''WITH\nDELETE''' . }",
            'SELECT ?x WHERE { ?x ?p "say \\"WITH\\"" . }',
            '# WITH a comment\nPREFIX b: <https://example.org/> SELECT ?x WHERE { ?x b:p ?v }',
        ]
        for query in queries:
            with self.subTest(query=query):self.assertIn('LIMIT 200',validate_read_only(query))

    def test_real_write_and_remote_service_commands_remain_rejected(self):
        for query in ('WITH <https://example.org/> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }',
                      'SELECT * WHERE { SERVICE <https://example.org/> { ?s ?p ?o } }',
                      'SELECT * WHERE {} ; INSERT DATA { <https://a> <https://b> "x" }'):
            with self.subTest(query=query), self.assertRaises(ValueError):validate_read_only(query)

    def test_limit_inside_text_does_not_remove_result_limit(self):
        self.assertTrue(validate_read_only('SELECT * WHERE {?s ?p "LIMIT 999"}').endswith('LIMIT 200'))

    def test_shot_style_spelling_and_supported_types(self):
        for question in ('Give all the alley-oop dunks of the game','Show allay oops','all alley oops','Show lay-ups'):
            self.assertTrue(unsupported_shot_style(question))
        self.assertFalse(unsupported_shot_style('Show assisted two-point shots and fast breaks'))

class MetadataEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_team_images_are_read_from_depiction_with_safe_fallback(self):
        rows=[{'team':{'value':'https://example.org/PAN'},'name':{'value':'Panathinaikos'},'logo':{'value':'https://cdn.example.org/pan.png'}},
              {'team':{'value':'https://example.org/MAD'},'name':{'value':'Real Madrid'},'logo':{'value':'javascript:bad'}}]
        with patch.object(backend,'query_sparql',AsyncMock(return_value={'results':{'bindings':rows}})) as query:
            result=await backend.get_teams()
        self.assertIn('foaf:depiction',query.call_args.args[0])
        self.assertEqual(result['teams'][0]['logo'],'https://cdn.example.org/pan.png')
        self.assertIsNone(result['teams'][1]['logo'])

    async def test_unsupported_styles_do_not_return_unrelated_two_pointers(self):
        with patch.object(backend,'generate_ai_search_text',AsyncMock()) as generate:
            result=await backend.ai_chat_handler(backend.ChatRequest(message='Give all the alley-oop dunks of the game',game_code='333',season_code='E2023',include_answer=True))
        generate.assert_not_called();self.assertEqual(result['results'],[])
        self.assertEqual(result['answer']['kind'],'capability')
        self.assertIn('does not mean',result['answer']['note'])

    async def test_invalid_query_is_retried_once_then_returns_a_plain_error(self):
        with patch.object(backend,'ai_search_configuration',return_value=('openai','ontology','test')),patch.object(backend,'generate_ai_search_text',AsyncMock(return_value=('SELECT * WHERE { SERVICE <https://x> {?s ?p ?o}}',{}))) as generate:
            with self.assertRaises(backend.HTTPException) as error:
                await backend.ai_chat_handler(backend.ChatRequest(message='List plays'))
        self.assertEqual(generate.await_count,2)
        self.assertEqual(error.exception.status_code,422)
        self.assertNotIn('SPARQL',error.exception.detail)
        self.assertNotIn('SERVICE',error.exception.detail)

    async def test_one_successful_repair_can_complete_search(self):
        with patch.object(backend,'ai_search_configuration',return_value=('openai','ontology','test')),patch.object(backend,'generate_ai_search_text',AsyncMock(side_effect=[('WITH invalid',{}),('SELECT ?name WHERE {?p ?label ?name} LIMIT 1',{})])) as generate,patch.object(backend,'query_sparql',AsyncMock(return_value={'results':{'bindings':[{'name':{'value':'Sloukas'}}]}})):
            result=await backend.ai_chat_handler(backend.ChatRequest(message='List one player'))
        self.assertEqual(generate.await_count,2);self.assertEqual(result['results'][0]['name']['value'],'Sloukas')

if __name__=='__main__':unittest.main()
