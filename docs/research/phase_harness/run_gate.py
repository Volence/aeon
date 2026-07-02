#!/usr/bin/env python3
"""Run oracle's determinism gate with a corrected ROM path (repo was renamed s4_engine->aeon)."""
import sys
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
import determinism_gate
determinism_gate.ROM = "/home/volence/sonic_hacks/aeon/s4.bin"
sys.exit(determinism_gate.main())
