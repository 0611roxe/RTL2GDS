import argparse
import sys
import os
from pathlib import Path
from typing import Optional

try:
    from simulator import Simulator
    from cpu_test import CpuTestLogParser
    from benchmark import BenchmarkLogParser
except ImportError as e:
    print(f"Error: Could not import a required class. Is the script path configured correctly?", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

import re

class MainWorkflow:
    def __init__(self, rtl_file: Path, stage: str, mainargs: str, tests: list[str], stage_template_file: Optional[Path] = None):
        self.rtl_file = rtl_file
        self.stage = stage
        self.mainargs = mainargs
        self.tests_to_run = tests
        self.stage_template_file = stage_template_file

        try:
            self.result_dir = Path(os.environ['RESULT_DIR'])
        except KeyError as e:
            print(f"Error: Required environment variable {e} is not set.", file=sys.stderr)
            print("The 'step_processor' should have injected this variable. Check your step.yaml.", file=sys.stderr)
            sys.exit(1)
        
        self.simulator: Optional[Simulator] = None

        soc_home = os.environ.get("SOC_HOME")
        if soc_home is None:
            raise RuntimeError("Environment variable SOC_HOME is not set")
        self.soc_v_path = Path(soc_home) / "ysyxSoCFull.v"
        self._soc_v_backup = None

        self.dstagecpu_sv_path = Path(soc_home) / "DSTAGECPU.sv"
        self._dstagecpu_sv_backup = None

    def _replace_top_name_in_soc_v(self):
        if not self.soc_v_path.exists():
            print(f"Warning: {self.soc_v_path} not found, skip replacement.", file=sys.stderr)
            return
        text = self.soc_v_path.read_text()
        self._soc_v_backup = text
        if self.stage.upper() == "D":
            new_top = "DSTAGECPU"
        else:
            new_top = os.environ.get("TOP_NAME", "ysyx_00000000")
        new_text, count = re.subn(r'ysyx_00000000', new_top, text)
        if count > 0:
            self.soc_v_path.write_text(new_text)
            print(f"Replaced ysyx_00000000 with {new_top} in {self.soc_v_path}")
        else:
            print(f"ysyx_00000000 not found in {self.soc_v_path}, no replacement made.", file=sys.stderr)

    def _restore_soc_v_file(self):
        if self._soc_v_backup is not None:
            self.soc_v_path.write_text(self._soc_v_backup)
            print(f"Restored {self.soc_v_path} to original ysyx_00000000.")

    def _replace_top_name_in_dstagecpu(self):
        if not self.dstagecpu_sv_path.exists():
            print(f"Warning: {self.dstagecpu_sv_path} not found, skip replacement.", file=sys.stderr)
            return
        text = self.dstagecpu_sv_path.read_text()
        self._dstagecpu_sv_backup = text
        new_top = os.environ.get("TOP_NAME", "ysyx_00000000")
        new_text, count = re.subn(r'ysyx_00000000', new_top, text)
        if count > 0:
            self.dstagecpu_sv_path.write_text(new_text)
            print(f"Replaced ysyx_00000000 with {new_top} in {self.dstagecpu_sv_path}")
        else:
            print(f"ysyx_00000000 not found in {self.dstagecpu_sv_path}, no replacement made.", file=sys.stderr)

    def _restore_dstagecpu_file(self):
        if self._dstagecpu_sv_backup is not None:
            self.dstagecpu_sv_path.write_text(self._dstagecpu_sv_backup)
            print(f"Restored {self.dstagecpu_sv_path} to original ysyx_00000000.")

    def execute(self) -> bool:
        if self.stage.upper() == 'D':
            self._replace_top_name_in_dstagecpu()
        self._replace_top_name_in_soc_v()
        try:
            self.simulator = Simulator(
                rtl_file=self.rtl_file, 
                top_name=os.environ.get("TOP_NAME", "ysyx_00000000")
            )
            if not self.simulator._build_simulator():
                print("\nAborting workflow due to simulator build failure.", file=sys.stderr)
                sys.exit(1)

            if 'all' in self.tests_to_run:
                selected_tests = self.simulator._discover_available_tests()
            else:
                selected_tests = self.tests_to_run
            
            if not selected_tests:
                print("\nNo tests were selected or discovered. Workflow finished.")
                return True 

            print(f"\nWorkflow will execute the following tests: {', '.join(selected_tests)}")
            tests_passed = self.simulator.run_tests(tests_to_run=selected_tests, mainargs=self.mainargs)

            if not tests_passed:
                print("\nWarning: Some tests failed. Proceeding with log parsing anyway.", file=sys.stderr)
            
            self.run_parsers(executed_tests=selected_tests)
            return tests_passed
        finally:
            if self.stage.upper() == 'D':
                self._restore_dstagecpu_file()
            self._restore_soc_v_file()

    def run_parsers(self, executed_tests: list[str]):
        tasks_to_parse = set()
        if any(t in executed_tests for t in ["cpu-tests"]):
            tasks_to_parse.add("cpu-test")
        if any(t in executed_tests for t in ["coremark", "dhrystone", "microbench"]):
            tasks_to_parse.add("benchmark")

        parser_map = {"cpu-test": CpuTestLogParser, "benchmark": BenchmarkLogParser}
        for task in tasks_to_parse:
            print(f"\nRunning parser for: {task}")
            parser_instance = parser_map[task](log_dir=str(self.result_dir))
            parser_instance.parse()

def main():
    parser = argparse.ArgumentParser(description="A unified workflow to run tests and then parse their logs.")
    parser.add_argument('--rtl_file', type=Path, required=True)
    parser.add_argument('--stage', type=str, required=True, choices=['B', 'D'])
    parser.add_argument('--tests', nargs='*', default=['all'])
    parser.add_argument('--mainargs', type=str, default='train')
    parser.add_argument('--Dstage_template', type=Path, default=None, help='Template file for D stage')

    args = parser.parse_args()

    workflow = MainWorkflow(
        rtl_file=args.rtl_file,
        stage=args.stage,
        mainargs=args.mainargs,
        tests=args.tests,
        stage_template_file=args.Dstage_template
    )
    
    all_tests_succeeded = workflow.execute()

    if all_tests_succeeded:
        print("\nWorkflow completed successfully.")
        sys.exit(0)
    else:
        print("\nWorkflow completed, but some tests failed.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()