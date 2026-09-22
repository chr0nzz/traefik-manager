import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, 'static', 'js', 'static-config.js'), encoding='utf-8').read()


def test_the_provider_is_registered_for_the_route_editor_only():
    assert 'registerCompletionItemProvider' in SRC
    assert SRC.count('registerCompletionItemProvider') == 1, \
        'one provider, registered once, or every reopen stacks another'
    assert 'if (_routeYamlCompletions) return;' in SRC


def test_every_pool_comes_from_the_install_and_none_are_invented():
    block = SRC[SRC.index('async function _collectRouteYamlNames'):]
    block = block[:block.index('\nfunction _routeYamlContextKind')]
    for source in ('_allMiddlewares', '_ensureServicesList', '_fetchEntrypointsCached',
                   "getElementById('certResolver')", '_namesFromEditor'):
        assert source in block, f'{source} is how the editor learns real names'
    for invented in ('websecure', 'noauth', 'default@', 'example'):
        assert f"'{invented}'" not in block, 'no completion may be hardcoded'


def test_no_schema_library_was_pulled_in():
    assert 'monaco-yaml' not in SRC, 'a Traefik schema that goes stale is worse than no schema'


def test_the_context_matches_the_three_places_names_are_referenced():
    block = SRC[SRC.index('function _routeYamlContextKind'):]
    block = block[:block.index('\nfunction _registerRouteYamlCompletions')]
    assert re.search(r'serversTransport:.*return .serversTransports.', block, re.S)
    assert re.search(r'service:.*return .services.', block, re.S)
    assert "return 'middlewares'" in block and "return 'entryPoints'" in block
    assert "return ''" in block, 'an unrecognised line offers nothing at all'


def test_tls_options_are_left_to_their_own_tab():
    block = SRC[SRC.index('function _routeYamlContextKind'):]
    block = block[:block.index('\nfunction _registerRouteYamlCompletions')]
    assert 'tlsOptions' not in block, 'TLS options are managed on their own tab, out of scope here'


def test_names_read_from_the_editor_only_take_direct_children():
    block = SRC[SRC.index('function _namesFromEditor'):]
    block = block[:block.index('\nasync function _collectRouteYamlNames')]
    assert 'pad === want + 2' in block, 'a nested key is not a definition name'
    assert 'if (pad <= want) break;' in block, 'the scan stops when the block ends'


def test_the_snippets_are_placeholders_not_invented_names():
    block = SRC[SRC.index('const _ROUTE_YAML_SNIPPETS'):]
    block = block[:block.index('\nfunction _registerRouteYamlCompletions')]
    for label in ('healthCheck', 'serversTransport', 'router'):
        assert f"label: '{label}'" in block
    assert block.count('${') >= 6, 'a snippet is a shape to fill in, with tab stops'
    assert 'InsertAsSnippet' in SRC, 'without the rule Monaco pastes the placeholder text literally'


def test_a_value_line_never_offers_a_snippet():
    block = SRC[SRC.index('function _registerRouteYamlCompletions'):]
    block = block[:block.index('\nfunction _initRouteYamlMonaco')]
    assert "if (!/^\\s*[A-Za-z]*$/.test(model.getLineContent(position.lineNumber))) return { suggestions: [] };" in block
