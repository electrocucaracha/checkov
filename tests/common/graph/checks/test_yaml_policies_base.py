import json
import os
import yaml
from abc import abstractmethod
from pathlib import Path
from typing import List
from unittest import TestCase

from checkov.common.checks_infra.checks_parser import NXGraphCheckParser
from checkov.common.checks_infra.registry import Registry
from checkov.common.graph.graph_manager import GraphManager
from checkov.common.output.record import Record
from checkov.runner_filter import RunnerFilter


class TestYamlPoliciesBase(TestCase):
    def __init__(self, graph_manager: GraphManager, checks, check_type, test_file_path, args):
        super().__init__(args)
        self.check_type = check_type
        self.checks = checks
        self.test_file_path = test_file_path
        self.graph_manager = graph_manager

    def go(self, dir_name, check_name=None):
        dir_path = os.path.join(os.path.dirname(os.path.realpath(self.test_file_path)),
                                f"resources/{dir_name}")
        assert os.path.exists(dir_path)
        policy_dir_path = os.path.dirname(self.checks.__file__)
        assert os.path.exists(policy_dir_path)
        found = False
        for root, d_names, f_names in os.walk(policy_dir_path):
            for f_name in f_names:
                check_name = dir_name if check_name is None else check_name
                if f_name == f"{check_name}.yaml":
                    found = True
                    policy = load_yaml_data(f_name, root)
                    assert policy is not None
                    expected = load_yaml_data("expected.yaml", dir_path)
                    assert expected is not None
                    report = self.get_policy_results(dir_path, policy)
                    expected = load_yaml_data("expected.yaml", dir_path)

                    expected_to_fail = expected.get('fail', [])
                    expected_to_pass = expected.get('pass', [])
                    expected_to_skip = expected.get('skip', [])
                    expected_evaluated_keys = expected.get('evaluated_keys', [])
                    self.assert_entities(expected_to_pass, report.passed_checks, True)
                    self.assert_entities(expected_to_fail, report.failed_checks, False)
                    self.assert_entities(expected_to_skip, report.skipped_checks, True)
                    self.assert_evaluated_keys(expected_evaluated_keys, report.passed_checks + report.failed_checks)

        assert found

    def assert_entities(self, expected_entities: List[str], results: List[Record], assertion: bool):
        self.assertEqual(len(expected_entities), len(results),
                         f"mismatch in number of results in {'passed' if assertion else 'failed'}, "
                         f"expected: {len(expected_entities)}, got: {len(results)}")
        for expected_entity in expected_entities:
            found = False
            for check_result in results:
                entity_id = check_result.resource
                if entity_id == expected_entity:
                    found = True
                    break
            self.assertTrue(found, f"expected to find entity {expected_entity}, {'passed' if assertion else 'failed'}")

    def get_policy_results(self, root_folder, policy):
        check_id = policy['metadata']['id']
        local_graph, _ = self.graph_manager.build_graph_from_source_directory(root_folder)
        nx_graph = self.graph_manager.save_graph(local_graph)
        registry = self.get_checks_registry()
        checks_results = registry.run_checks(nx_graph, RunnerFilter(checks=[check_id]))
        return self.create_report_from_graph_checks_results(checks_results, policy['metadata'])

    def get_checks_registry(self):
        registry = Registry(parser=NXGraphCheckParser(), checks_dir=str(
            Path(
                self.test_file_path).parent.parent.parent.parent.parent / "checkov" / self.check_type / "checks" / "graph_checks"))
        registry.load_checks()
        return registry

    @abstractmethod
    def create_report_from_graph_checks_results(self, checks_results, check):
        pass

    @abstractmethod
    def assert_evaluated_keys(self, checks_results, check):
        pass


def load_yaml_data(source_file_name, dir_path):
    expected_path = os.path.join(dir_path, source_file_name)
    if not os.path.exists(expected_path):
        return None

    with open(expected_path, "r") as f:
        expected_data = yaml.safe_load(f)

    return json.loads(json.dumps(expected_data))
