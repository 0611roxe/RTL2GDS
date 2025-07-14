import shutil
import re
from pathlib import Path
from typing import List, Tuple

def parse_ports(port_list_str):
    ports = []
    cur_dir = None
    cur_width = ""
    for line in port_list_str.splitlines():
        # Remove comments and trailing commas
        line = line.split('//')[0].strip().rstrip(',')
        if not line: continue
        # Match broad direction lines with possibly multiple signals
        m = re.match(r'(input|output|inout)\s*(?:reg|wire)?\s*(\[[^\]]+\])?\s*(.*)', line)
        if m:
            cur_dir = m.group(1)
            cur_width = m.group(2) or ""
            names = m.group(3)
        else:
            names = line
        # Split multiple names
        for part in names.split(','):
            pname = part.strip()
            if not pname: continue
            # Each part may have width before name (e.g. [31:0] foo)
            n = re.match(r'(\[[^\]]+\])?\s*([a-zA-Z_][a-zA-Z0-9_]*)$', pname)
            if n:
                width = n.group(1) or cur_width
                name = n.group(2)
                ports.append((cur_dir, width, name))
    return ports

class VerilogModuleInfo:
    def __init__(self, name: str, ports: List[Tuple[str, str, str]]):
        self.name = name
        self.ports = ports  # List of (direction, width, name)

    @classmethod
    def from_file(cls, file_path: Path, target_module: str):
        text = file_path.read_text()
        module_re = re.compile(
            r"module\s+{}\s*\((.*?)\)\s*;".format(re.escape(target_module)),
            re.DOTALL | re.MULTILINE
        )
        match = module_re.search(text)
        if not match:
            return None
        port_list_str = match.group(1)
        ports = parse_ports(port_list_str)
        return cls(target_module, ports)

class BusWrapper:
    def __init__(
        self,
        core_path: Path,
        bridge_path: Path,
        outdir: Path,
        core_module_name: str
    ):
        self.core_path = Path(core_path)
        self.bridge_path = Path(bridge_path)
        self.outdir = Path(outdir)
        self.core_module_name = core_module_name
        self.core_mod = None
        self.bridge_mod = None
        self.axi_top_path = self.outdir / "axi_top.v"

    def extract_modules(self):
        self.core_mod = VerilogModuleInfo.from_file(self.core_path, target_module=self.core_module_name)
        self.bridge_mod = VerilogModuleInfo.from_file(self.bridge_path, target_module="MemBridge")
        if self.core_mod is None:
            raise ValueError(f"Module '{self.core_module_name}' not found in {self.core_path}")
        if self.bridge_mod is None:
            raise ValueError(f"Module 'MemBridge' not found in {self.bridge_path}")

    def copy_files(self):
        self.outdir.mkdir(exist_ok=True, parents=True)
        shutil.copy2(self.core_path, self.outdir / self.core_path.name)
        shutil.copy2(self.bridge_path, self.outdir / self.bridge_path.name)

    def get_port_dict(self, mod: VerilogModuleInfo) -> dict:
        # name -> (direction, width)
        return {name: (direction, width) for direction, width, name in mod.ports}

    def get_axi_top_ports(self) -> List[Tuple[str, str, str]]:
        core_ports = self.get_port_dict(self.core_mod)
        bridge_ports = self.get_port_dict(self.bridge_mod)
        rv_ports = [(direction, width, name) for name, (direction, width) in core_ports.items()
                    if name in ("clock", "reset", "io_interrupt")]
        mb_ports = [(direction, width, name) for name, (direction, width) in bridge_ports.items()
                    if name.startswith("io_out_")]
        port_dict = {name: (direction, width) for direction, width, name in rv_ports + mb_ports}
        return [(direction, width, name) for name, (direction, width) in port_dict.items()]

    def get_internal_wires(self) -> List[Tuple[str, str]]:
        top_port_names = set(name for _, _, name in self.get_axi_top_ports())
        core_ports = self.get_port_dict(self.core_mod)
        bridge_ports = self.get_port_dict(self.bridge_mod)
        wire_ports = []
        for name in sorted((set(core_ports.keys()) & set(bridge_ports.keys())) - top_port_names):
            width = core_ports[name][1] or bridge_ports[name][1] or ""
            wire_ports.append((name, width))
        return wire_ports

    def generate_axi_top(self):
        top_ports = self.get_axi_top_ports()
        wire_ports = self.get_internal_wires()
        top_ports_decl = ",\n    ".join([
            f"{direction} wire {width + ' ' if width else ''}{name}" for direction, width, name in top_ports
        ])
        wire_decl = ""
        for name, width in wire_ports:
            wire_decl += f"    wire {width + ' ' if width else ''}{name};\n"

        def gen_instance(mod: VerilogModuleInfo):
            port_dict = self.get_port_dict(mod)
            port_conns = []
            top_names = set(name for _, _, name in top_ports)
            wire_names = set(name for name, _ in wire_ports)
            for name in port_dict:
                if name in top_names:
                    port_conns.append(f".{name}({name})")
                elif name in wire_names:
                    port_conns.append(f".{name}({name})")
                else:
                    port_conns.append(f".{name}()")
            port_conns_str = ',\n        '.join(port_conns)
            return f"{mod.name} u_{mod.name} (\n        {port_conns_str}\n    );"

        core_inst = gen_instance(self.core_mod)
        bridge_inst = gen_instance(self.bridge_mod)

        axi_top_content = f"""\
/*
 * Auto-generated by BusWrapper.
 */
`include "{self.core_path.name}"
`include "{self.bridge_path.name}"

module axi_top(
    {top_ports_decl}
);

{wire_decl}
    // Instance of {self.core_mod.name}
    {core_inst}

    // Instance of {self.bridge_mod.name}
    {bridge_inst}

endmodule
"""
        self.axi_top_path.write_text(axi_top_content)

    def run(self):
        self.extract_modules()
        self.copy_files()
        self.generate_axi_top()
        return self.axi_top_path, "axi_top"