#!/usr/bin/env python3
"""
Tests for s4lint — Sonic 4 Engine 68000 assembly linter.

Run with: python3 -m pytest tools/test_s4lint.py -v
      or: python3 tools/test_s4lint.py
"""

import sys
import os
import io
import contextlib
import tempfile
import unittest

# Allow running from the aeon root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.s4lint import (
    tokenize_line, Token, Diagnostic, LintContext,
    parse_numeric, _extract_address_value,
    check_e001, check_e002, check_e003, check_e004,
    check_e005_track, _count_dc_b_items, _count_ds_b_items,
    run_checks, _parse_suppressed,
    check_warnings,
    _is_dreg, _is_areg, _is_memory_operand, _parse_immediate,
    lint_file,
    main as s4lint_main,
    DIAGNOSTIC_SEVERITY,
)


class TestTokenizer(unittest.TestCase):

    # ------------------------------------------------------------------
    # Basic instructions
    # ------------------------------------------------------------------

    def test_instruction_with_size_and_operands(self):
        tok = tokenize_line("    move.w  d0, (a0)+")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["d0", "(a0)+"])
        self.assertEqual(tok.comment, "")

    def test_no_size_instruction(self):
        """rts has no size suffix."""
        tok = tokenize_line("        rts")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "rts")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "")

    def test_instruction_with_comment(self):
        tok = tokenize_line("        rts                    ; return")
        self.assertEqual(tok.instruction, "rts")
        self.assertEqual(tok.comment, "; return")

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def test_global_label_alone(self):
        tok = tokenize_line("EntryPoint:")
        self.assertEqual(tok.label, "EntryPoint")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])

    def test_local_label_alone(self):
        tok = tokenize_line(".wait_z80:")
        self.assertEqual(tok.label, ".wait_z80")
        self.assertEqual(tok.instruction, "")

    def test_indented_local_label(self):
        """Local labels may appear indented in this codebase."""
        tok = tokenize_line("    .loop:")
        self.assertEqual(tok.label, ".loop")
        self.assertEqual(tok.instruction, "")

    def test_label_plus_instruction(self):
        """Label + instruction on same line."""
        tok = tokenize_line("Init:   moveq   #0, d0")
        self.assertEqual(tok.label, "Init")
        self.assertEqual(tok.instruction, "moveq")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, ["#0", "d0"])

    def test_label_plus_sized_instruction(self):
        tok = tokenize_line("Cold_Boot: move.l  #$53454741, (TMSS_REGISTER).l")
        self.assertEqual(tok.label, "Cold_Boot")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["#$53454741", "(TMSS_REGISTER).l"])

    # ------------------------------------------------------------------
    # Comments and blank lines
    # ------------------------------------------------------------------

    def test_comment_only_line(self):
        tok = tokenize_line("; This is a comment")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "; This is a comment")

    def test_blank_line(self):
        tok = tokenize_line("")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])
        self.assertEqual(tok.comment, "")

    def test_whitespace_only_line(self):
        tok = tokenize_line("    ")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "")
        self.assertEqual(tok.operands, [])

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------

    def test_dc_w(self):
        tok = tokenize_line("    dc.w    $0000")
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["$0000"])

    def test_dc_b(self):
        tok = tokenize_line('    dc.b    "SEGA GENESIS    "')
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".b")
        # The string is one operand
        self.assertTrue(any('"SEGA GENESIS    "' in op for op in tok.operands))

    def test_dc_l_multiple(self):
        tok = tokenize_line("    dc.l    SYSTEM_STACK, EntryPoint")
        self.assertEqual(tok.instruction, "dc")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["SYSTEM_STACK", "EntryPoint"])

    def test_ds_b(self):
        tok = tokenize_line("vdp_mode1               ds.b 1")
        self.assertEqual(tok.label, "vdp_mode1")
        self.assertEqual(tok.instruction, "ds")
        self.assertEqual(tok.size, ".b")
        self.assertEqual(tok.operands, ["1"])

    def test_include_directive(self):
        tok = tokenize_line('    include "constants.asm"')
        self.assertEqual(tok.instruction, "include")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, ['"constants.asm"'])

    def test_even_directive(self):
        tok = tokenize_line("    even")
        self.assertEqual(tok.instruction, "even")
        self.assertEqual(tok.operands, [])

    def test_align_directive(self):
        tok = tokenize_line("    align 2")
        self.assertEqual(tok.instruction, "align")
        self.assertEqual(tok.operands, ["2"])

    def test_org_directive(self):
        tok = tokenize_line("    org 0")
        self.assertEqual(tok.instruction, "org")
        self.assertEqual(tok.operands, ["0"])

    def test_cpu_directive(self):
        tok = tokenize_line("    cpu 68000")
        self.assertEqual(tok.instruction, "cpu")
        self.assertEqual(tok.operands, ["68000"])

    def test_set_directive(self):
        """AS `set` directive — not a 68K instruction."""
        tok = tokenize_line("    set .c, 0")
        self.assertEqual(tok.instruction, "set")
        self.assertEqual(tok.operands, [".c", "0"])

    def test_error_directive(self):
        tok = tokenize_line('    error "ROM size is odd"')
        self.assertEqual(tok.instruction, "error")
        self.assertTrue(any('"ROM size is odd"' in op for op in tok.operands))

    def test_if_directive(self):
        tok = tokenize_line("    if (EndOfRom & 1) <> 0")
        self.assertEqual(tok.instruction, "if")
        self.assertGreater(len(tok.operands), 0)

    def test_endif_directive(self):
        tok = tokenize_line("    endif")
        self.assertEqual(tok.instruction, "endif")
        self.assertEqual(tok.operands, [])

    def test_ifdef_directive(self):
        tok = tokenize_line("    ifdef _dplc_ptr")
        self.assertEqual(tok.instruction, "ifdef")
        self.assertEqual(tok.operands, ["_dplc_ptr"])

    def test_ifndef_directive(self):
        tok = tokenize_line("    ifndef _dplc_ptr")
        self.assertEqual(tok.instruction, "ifndef")
        self.assertEqual(tok.operands, ["_dplc_ptr"])

    def test_rept_directive(self):
        tok = tokenize_line("    rept 4")
        self.assertEqual(tok.instruction, "rept")
        self.assertEqual(tok.operands, ["4"])

    def test_endr_directive(self):
        tok = tokenize_line("    endr")
        self.assertEqual(tok.instruction, "endr")

    def test_struct_directive(self):
        """AS struct: label before the directive keyword."""
        tok = tokenize_line("VDP_Shadow struct")
        self.assertEqual(tok.label, "VDP_Shadow")
        self.assertEqual(tok.instruction, "struct")
        self.assertEqual(tok.operands, [])

    def test_endstruct_directive(self):
        tok = tokenize_line("VDP_Shadow endstruct")
        self.assertEqual(tok.label, "VDP_Shadow")
        self.assertEqual(tok.instruction, "endstruct")

    def test_binclude_directive(self):
        """Uppercase BINCLUDE variant used in this codebase."""
        tok = tokenize_line('    BINCLUDE "data/mappings/sonic.bin"')
        self.assertEqual(tok.instruction, "BINCLUDE")
        self.assertTrue(any('"data/mappings/sonic.bin"' in op for op in tok.operands))

    def test_phase_directive(self):
        tok = tokenize_line("    phase $FF0000")
        self.assertEqual(tok.instruction, "phase")
        self.assertEqual(tok.operands, ["$FF0000"])

    def test_dephase_directive(self):
        tok = tokenize_line("    dephase")
        self.assertEqual(tok.instruction, "dephase")
        self.assertEqual(tok.operands, [])

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def test_macro_no_args(self):
        """stopZ80 is a macro — preserve case, no operands."""
        tok = tokenize_line("        stopZ80")
        self.assertEqual(tok.label, "")
        self.assertEqual(tok.instruction, "stopZ80")
        self.assertEqual(tok.size, "")
        self.assertEqual(tok.operands, [])

    def test_macro_with_args(self):
        """setVDPReg macro with two arguments."""
        tok = tokenize_line("        setVDPReg VDP_Shadow_vdp_mode2, #$34")
        self.assertEqual(tok.instruction, "setVDPReg")
        self.assertEqual(tok.operands, ["VDP_Shadow_vdp_mode2", "#$34"])

    # ------------------------------------------------------------------
    # Operand splitting edge cases
    # ------------------------------------------------------------------

    def test_operand_parens_not_split(self):
        """Parenthesised addressing modes must not be split on inner comma."""
        tok = tokenize_line("        move.l  (a0,d0.w), d1")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["(a0,d0.w)", "d1"])

    def test_movem_register_list(self):
        """movem register list — dash is fine, comma separates two operands."""
        tok = tokenize_line("        movem.l d0-a6, -(sp)")
        self.assertEqual(tok.instruction, "movem")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["d0-a6", "-(sp)"])

    def test_nested_parens(self):
        """Function calls in operands — e.g. #vram_art(VRAM_X,0,0)."""
        tok = tokenize_line("        move.w  #vram_art(VRAM_Sonic,0,0), SST_art_tile(a0)")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["#vram_art(VRAM_Sonic,0,0)", "SST_art_tile(a0)"])

    # ------------------------------------------------------------------
    # Assignment / EQU lines
    # ------------------------------------------------------------------

    def test_simple_assignment(self):
        """MY_CONST = $50 — label is lvalue, instruction is '='."""
        tok = tokenize_line("MY_CONST = $50")
        self.assertEqual(tok.label, "MY_CONST")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["$50"])

    def test_assignment_with_expression(self):
        """Assignment where the rhs references another constant."""
        tok = tokenize_line("_enemy_patrol_left = SST_sst_custom")
        self.assertEqual(tok.label, "_enemy_patrol_left")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["SST_sst_custom"])

    def test_assignment_with_offset(self):
        tok = tokenize_line("_art_base       = SST_sst_custom+4")
        self.assertEqual(tok.label, "_art_base")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["SST_sst_custom+4"])

    def test_padToPowerOfTwo_assignment(self):
        """Top-level flag assignment from main.asm."""
        tok = tokenize_line("padToPowerOfTwo         = 1")
        self.assertEqual(tok.label, "padToPowerOfTwo")
        self.assertEqual(tok.instruction, "=")
        self.assertEqual(tok.operands, ["1"])

    # ------------------------------------------------------------------
    # Lint suppression comment
    # ------------------------------------------------------------------

    def test_suppress_comment_recognized(self):
        """'; lint: disable=E002' is captured verbatim in comment field."""
        tok = tokenize_line("        rts                    ; lint: disable=E002")
        self.assertEqual(tok.instruction, "rts")
        self.assertIn("lint: disable=E002", tok.comment)

    # ------------------------------------------------------------------
    # Real patterns from this codebase
    # ------------------------------------------------------------------

    def test_dbf_instruction(self):
        tok = tokenize_line("        dbf     d1, .vdp_loop")
        self.assertEqual(tok.instruction, "dbf")
        self.assertEqual(tok.operands, ["d1", ".vdp_loop"])

    def test_bne_local_label(self):
        tok = tokenize_line("        bne.s   .wait_z80")
        self.assertEqual(tok.instruction, "bne")
        self.assertEqual(tok.size, ".s")
        self.assertEqual(tok.operands, [".wait_z80"])

    def test_lea_instruction(self):
        tok = tokenize_line("        lea     (Object_RAM).w, a0")
        self.assertEqual(tok.instruction, "lea")
        self.assertEqual(tok.operands, ["(Object_RAM).w", "a0"])

    def test_move_with_absolute_long(self):
        tok = tokenize_line("        move.w  (Z80_BUS_REQUEST).l, d0")
        self.assertEqual(tok.instruction, "move")
        self.assertEqual(tok.size, ".w")
        self.assertEqual(tok.operands, ["(Z80_BUS_REQUEST).l", "d0"])

    def test_btst_instruction(self):
        tok = tokenize_line("        btst    #0, (Z80_BUS_REQUEST).l")
        self.assertEqual(tok.instruction, "btst")
        self.assertEqual(tok.operands, ["#0", "(Z80_BUS_REQUEST).l"])

    def test_movem_restore(self):
        tok = tokenize_line("        movem.l (sp)+, d0-d2/a1")
        self.assertEqual(tok.instruction, "movem")
        self.assertEqual(tok.size, ".l")
        self.assertEqual(tok.operands, ["(sp)+", "d0-d2/a1"])

    def test_jsr_instruction(self):
        tok = tokenize_line("        jsr     AllocDynamic")
        self.assertEqual(tok.instruction, "jsr")
        self.assertEqual(tok.operands, ["AllocDynamic"])

    def test_exg_instruction(self):
        tok = tokenize_line("        exg     a1, a2")
        self.assertEqual(tok.instruction, "exg")
        self.assertEqual(tok.operands, ["a1", "a2"])

    def test_macro_definition_line(self):
        """'stopZ80 macro' — the macro keyword itself."""
        tok = tokenize_line("stopZ80 macro")
        self.assertEqual(tok.label, "stopZ80")
        self.assertEqual(tok.instruction, "macro")
        self.assertEqual(tok.operands, [])

    def test_endm_directive(self):
        tok = tokenize_line("        endm")
        self.assertEqual(tok.instruction, "endm")
        self.assertEqual(tok.operands, [])

    def test_padding_off(self):
        tok = tokenize_line("    padding off")
        self.assertEqual(tok.instruction, "padding")
        self.assertEqual(tok.operands, ["off"])

    def test_supmode_on(self):
        tok = tokenize_line("    supmode on")
        self.assertEqual(tok.instruction, "supmode")
        self.assertEqual(tok.operands, ["on"])

    def test_function_definition(self):
        """AS `function` keyword — multi-line via backslash not tested here,
        just the first line."""
        tok = tokenize_line("vdpComm     function addr,type,rwd, \\")
        self.assertEqual(tok.label, "vdpComm")
        self.assertEqual(tok.instruction, "function")

    def test_line_with_comment_semicolon_in_string(self):
        """Semicolon inside a string literal must NOT start a comment."""
        tok = tokenize_line('    dc.b    "SEGA; GENESIS"   ; comment')
        self.assertEqual(tok.instruction, "dc")
        self.assertIn("; comment", tok.comment)
        # The operand should contain the full string including the semicolon
        self.assertTrue(any('"SEGA; GENESIS"' in op for op in tok.operands))


class TestDiagnostic(unittest.TestCase):

    def test_str_format(self):
        d = Diagnostic("boot.asm", 42, "error", "E001", "unsized branch detected")
        self.assertEqual(str(d), "boot.asm:42: error: unsized branch detected [E001]")

    def test_warning_format(self):
        d = Diagnostic("core.asm", 7, "warning", "W003", "possible fall-through")
        self.assertEqual(str(d), "core.asm:7: warning: possible fall-through [W003]")


class TestLintContext(unittest.TestCase):

    def test_emit_adds_diagnostic(self):
        ctx = LintContext("boot.asm", {})
        ctx.emit("error", "E001", 10, "test message")
        self.assertEqual(len(ctx.diagnostics), 1)
        self.assertEqual(ctx.diagnostics[0].code, "E001")
        self.assertEqual(ctx.diagnostics[0].severity, "error")

    def test_reset_routine_state(self):
        ctx = LintContext("boot.asm", {})
        ctx.z80_state = "stopped"
        ctx.ints_state = "disabled"
        ctx.sr_saved = True
        ctx.reset_routine_state()
        self.assertEqual(ctx.z80_state, "running")
        self.assertEqual(ctx.ints_state, "enabled")
        self.assertFalse(ctx.sr_saved)

    def test_initial_state(self):
        ctx = LintContext("boot.asm", {})
        self.assertEqual(ctx.z80_state, "running")
        self.assertEqual(ctx.ints_state, "enabled")
        self.assertFalse(ctx.sr_saved)
        self.assertFalse(ctx.in_struct)
        self.assertEqual(ctx.in_rept, 0)
        self.assertFalse(ctx.in_macro_def)


# ---------------------------------------------------------------------------
# Helpers for check tests
# ---------------------------------------------------------------------------

def _make_ctx(filepath="engine/core.asm"):
    """Create a minimal LintContext for check tests."""
    return LintContext(filepath, {})


def _run_check(check_fn, line_text, filepath="engine/core.asm", suppressed=None):
    """Tokenize *line_text*, run *check_fn*, return list of diagnostics."""
    if suppressed is None:
        suppressed = set()
    ctx = _make_ctx(filepath)
    tok = tokenize_line(line_text)
    check_fn(ctx, tok, 1, suppressed)
    return ctx.diagnostics


# ---------------------------------------------------------------------------
# parse_numeric / _extract_address_value helpers
# ---------------------------------------------------------------------------

class TestParseNumeric(unittest.TestCase):

    def test_hex_dollar(self):
        self.assertEqual(parse_numeric("$C00000"), 0xC00000)

    def test_hex_lowercase(self):
        self.assertEqual(parse_numeric("$ff0000"), 0xFF0000)

    def test_decimal(self):
        self.assertEqual(parse_numeric("42"), 42)

    def test_odd_hex(self):
        self.assertEqual(parse_numeric("$C00001"), 0xC00001)

    def test_non_numeric_returns_none(self):
        self.assertIsNone(parse_numeric("MyLabel"))

    def test_expression_returns_none(self):
        self.assertIsNone(parse_numeric("$FF0000+4"))

    def test_zero(self):
        self.assertEqual(parse_numeric("0"), 0)


class TestExtractAddressValue(unittest.TestCase):

    def test_plain_hex(self):
        self.assertEqual(_extract_address_value("$FF0000"), 0xFF0000)

    def test_parens_with_suffix(self):
        self.assertEqual(_extract_address_value("($C00004).l"), 0xC00004)

    def test_parens_without_suffix(self):
        self.assertEqual(_extract_address_value("($FF0000)"), 0xFF0000)

    def test_w_suffix_no_parens(self):
        self.assertEqual(_extract_address_value("$FF0000.w"), 0xFF0000)

    def test_symbolic_returns_none(self):
        self.assertIsNone(_extract_address_value("(VDP_CTRL).l"))

    def test_symbolic_plain_returns_none(self):
        self.assertIsNone(_extract_address_value("Object_RAM"))

    def test_immediate_hash_returns_none(self):
        """Immediate operands (#value) are not addresses — ignore."""
        self.assertIsNone(_extract_address_value("#$C00000"))


# ---------------------------------------------------------------------------
# E001: Unsized branch or jump
# ---------------------------------------------------------------------------

class TestE001_UnsizedBranch(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e001, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E001"]

    # --- should fire ---

    def test_bra_no_size(self):
        errs = self._errors("        bra     .loop")
        self.assertEqual(len(errs), 1)
        self.assertIn("bra", errs[0].message)

    def test_beq_no_size(self):
        errs = self._errors("        beq     .done")
        self.assertEqual(len(errs), 1)

    def test_bne_no_size(self):
        errs = self._errors("        bne     .retry")
        self.assertEqual(len(errs), 1)

    def test_bsr_no_size(self):
        errs = self._errors("        bsr     Subroutine")
        self.assertEqual(len(errs), 1)

    def test_bhi_no_size(self):
        errs = self._errors("        bhi     .over")
        self.assertEqual(len(errs), 1)

    def test_bmi_no_size(self):
        errs = self._errors("        bmi     .neg")
        self.assertEqual(len(errs), 1)

    def test_bcc_no_size(self):
        errs = self._errors("        bcc     .ok")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_bra_s_ok(self):
        errs = self._errors("        bra.s   .loop")
        self.assertEqual(len(errs), 0)

    def test_bne_w_ok(self):
        errs = self._errors("        bne.w   .far_label")
        self.assertEqual(len(errs), 0)

    def test_beq_s_ok(self):
        errs = self._errors("        beq.s   .done")
        self.assertEqual(len(errs), 0)

    def test_jmp_not_checked(self):
        """jmp is always long — not in the E001 set."""
        errs = self._errors("        jmp     (a0)")
        self.assertEqual(len(errs), 0)

    def test_jsr_not_checked(self):
        errs = self._errors("        jsr     SomeRoutine")
        self.assertEqual(len(errs), 0)

    def test_dbf_not_checked(self):
        errs = self._errors("        dbf     d1, .loop")
        self.assertEqual(len(errs), 0)

    def test_dbra_not_checked(self):
        errs = self._errors("        dbra    d0, .wait")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e001(self):
        errs = self._errors("        bra     .loop", suppressed={"E001"})
        self.assertEqual(len(errs), 0)

    def test_non_branch_not_checked(self):
        errs = self._errors("        move.w  d0, d1")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E002: Multiply / divide in hot path
# ---------------------------------------------------------------------------

class TestE002_MultiplyDivide(unittest.TestCase):

    def _diags(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e002, line, filepath, suppressed or set())
        return diags

    # --- engine/ → error ---

    def test_mulu_in_engine_is_error(self):
        diags = self._diags("        mulu    #8, d0", filepath="engine/core.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_muls_in_engine_is_error(self):
        diags = self._diags("        muls    d1, d0", filepath="engine/physics.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divu_in_engine_is_error(self):
        diags = self._diags("        divu    #10, d0", filepath="engine/math.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divs_in_engine_is_error(self):
        diags = self._diags("        divs    d2, d1", filepath="engine/scroll.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    # --- objects/ → error ---

    def test_mulu_in_objects_is_error(self):
        diags = self._diags("        mulu    #4, d0", filepath="objects/player.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_divs_in_objects_is_error(self):
        diags = self._diags("        divs    d0, d1", filepath="objects/enemy.asm")
        errs = [d for d in diags if d.code == "E002" and d.severity == "error"]
        self.assertEqual(len(errs), 1)

    # --- other directories → warning W014 ---

    def test_mulu_in_init_is_warning(self):
        diags = self._diags("        mulu    #8, d0", filepath="init/boot.asm")
        warns = [d for d in diags if d.code == "W014" and d.severity == "warning"]
        self.assertEqual(len(warns), 1)

    def test_muls_in_data_is_warning(self):
        diags = self._diags("        muls    d0, d1", filepath="data/tables.asm")
        warns = [d for d in diags if d.code == "W014" and d.severity == "warning"]
        self.assertEqual(len(warns), 1)

    # --- not flagged ---

    def test_add_not_flagged(self):
        diags = self._diags("        add.w   d0, d1", filepath="engine/core.asm")
        self.assertEqual(len(diags), 0)

    def test_suppressed_e002(self):
        diags = self._diags("        mulu    #8, d0", filepath="engine/core.asm",
                             suppressed={"E002"})
        errs = [d for d in diags if d.code == "E002"]
        self.assertEqual(len(errs), 0)

    def test_suppressed_w014(self):
        diags = self._diags("        mulu    #8, d0", filepath="init/boot.asm",
                             suppressed={"W014"})
        warns = [d for d in diags if d.code == "W014"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# E003: Odd immediate address
# ---------------------------------------------------------------------------

class TestE003_OddAddress(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e003, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E003"]

    # --- should fire ---

    def test_lea_odd_address(self):
        errs = self._errors("        lea     ($FF0001).l, a0")
        self.assertEqual(len(errs), 1)

    def test_movea_odd_address(self):
        errs = self._errors("        movea.l ($C00003).l, a1")
        self.assertEqual(len(errs), 1)

    def test_jmp_odd_address(self):
        errs = self._errors("        jmp     ($1001).l")
        self.assertEqual(len(errs), 1)

    def test_jsr_odd_address(self):
        errs = self._errors("        jsr     ($1003).l")
        self.assertEqual(len(errs), 1)

    def test_lea_odd_plain_hex(self):
        errs = self._errors("        lea     $FF0001, a0")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_lea_even_address(self):
        errs = self._errors("        lea     ($FF0000).l, a0")
        self.assertEqual(len(errs), 0)

    def test_movea_even_address(self):
        errs = self._errors("        movea.l ($C00004).l, a1")
        self.assertEqual(len(errs), 0)

    def test_lea_symbolic_not_flagged(self):
        errs = self._errors("        lea     (Object_RAM).w, a0")
        self.assertEqual(len(errs), 0)

    def test_movea_symbolic_not_flagged(self):
        errs = self._errors("        movea.l (VDP_CTRL).l, a0")
        self.assertEqual(len(errs), 0)

    def test_move_not_checked_by_e003(self):
        """E003 only checks movea/lea/jmp/jsr — plain move is E004 territory."""
        errs = self._errors("        move.w  ($C00001).l, d0")
        self.assertEqual(len(errs), 0)

    def test_movea_immediate_odd_fires(self):
        """movea.l #$FF0001, a0 — odd immediate loaded into address register."""
        errs = self._errors("        movea.l #$FF0001, a0")
        self.assertEqual(len(errs), 1)

    def test_movea_immediate_even_ok(self):
        errs = self._errors("        movea.l #$FF0000, a0")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e003(self):
        errs = self._errors("        lea     ($FF0001).l, a0", suppressed={"E003"})
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E004: Word/long access to odd literal address
# ---------------------------------------------------------------------------

class TestE004_OddWordAccess(unittest.TestCase):

    def _errors(self, line, filepath="engine/core.asm", suppressed=None):
        diags = _run_check(check_e004, line, filepath, suppressed or set())
        return [d for d in diags if d.code == "E004"]

    # --- should fire ---

    def test_move_w_odd_src(self):
        errs = self._errors("        move.w  ($C00001).l, d0")
        self.assertEqual(len(errs), 1)

    def test_move_w_odd_dst(self):
        errs = self._errors("        move.w  d0, ($C00001).l")
        self.assertEqual(len(errs), 1)

    def test_move_l_odd_address(self):
        errs = self._errors("        move.l  ($FF0003).l, d0")
        self.assertEqual(len(errs), 1)

    def test_add_w_odd_address(self):
        errs = self._errors("        add.w   ($FF0001).l, d0")
        self.assertEqual(len(errs), 1)

    def test_move_w_plain_odd_hex(self):
        errs = self._errors("        move.w  $FF0001, d0")
        self.assertEqual(len(errs), 1)

    # --- should NOT fire ---

    def test_move_b_odd_ok(self):
        """Byte access to odd address is legal."""
        errs = self._errors("        move.b  ($C00001).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_w_even_ok(self):
        errs = self._errors("        move.w  ($C00004).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_l_even_ok(self):
        errs = self._errors("        move.l  ($FF0000).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_w_symbolic_not_flagged(self):
        errs = self._errors("        move.w  (VDP_DATA).l, d0")
        self.assertEqual(len(errs), 0)

    def test_move_no_size_not_flagged(self):
        """Without explicit .w or .l size we cannot determine access width."""
        errs = self._errors("        move    d0, d1")
        self.assertEqual(len(errs), 0)

    def test_suppressed_e004(self):
        errs = self._errors("        move.w  ($C00001).l, d0", suppressed={"E004"})
        self.assertEqual(len(errs), 0)

    def test_dc_w_not_checked(self):
        """dc.w is a directive, not an instruction accessing memory."""
        errs = self._errors("        dc.w    $0001")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E005: Missing alignment after byte data
# ---------------------------------------------------------------------------

class TestE005_MissingEven(unittest.TestCase):
    """Tests for E005: dc.w/dc.l/ds.w/ds.l or 68K instruction after an odd
    number of dc.b/ds.b bytes without an intervening even/align."""

    def _lint_lines(self, lines_str: str):
        """Process multi-line assembly string; return list of E005 Diagnostics."""
        ctx = LintContext("test.asm", {})
        for line_num, raw_line in enumerate(lines_str.split("\n"), start=1):
            token = tokenize_line(raw_line)
            run_checks(ctx, token, line_num, raw_line, set())
        return [d for d in ctx.diagnostics if d.code == "E005"]

    # --- helper unit tests ---

    def test_count_dc_b_simple(self):
        self.assertEqual(_count_dc_b_items(["1", "2", "3"]), 3)

    def test_count_dc_b_string(self):
        self.assertEqual(_count_dc_b_items(['\"SEGA\"']), 4)

    def test_count_dc_b_mixed(self):
        self.assertEqual(_count_dc_b_items(["0", '\"SEGA\"']), 5)

    def test_count_ds_b_decimal(self):
        self.assertEqual(_count_ds_b_items(["3"]), 3)

    def test_count_ds_b_hex(self):
        self.assertEqual(_count_ds_b_items(["$04"]), 4)

    def test_count_ds_b_unknown_returns_zero(self):
        self.assertEqual(_count_ds_b_items(["SYMBOL"]), 0)

    # --- integration tests ---

    def test_odd_dc_b_then_dc_w_fires(self):
        """1 dc.b byte followed by dc.w -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_even_dc_b_then_dc_w_ok(self):
        """2 dc.b bytes then dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1, 2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_odd_dc_b_even_dc_w_ok(self):
        """1 dc.b byte + even -> dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    even\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_odd_dc_b_align2_dc_w_ok(self):
        """1 dc.b byte + align 2 -> dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    align 2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_ds_b_odd_count_then_dc_w_fires(self):
        """ds.b 3 (odd) then dc.w -> E005."""
        errs = self._lint_lines("Routine:\n    ds.b    3\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_ds_b_even_count_then_dc_w_ok(self):
        """ds.b 4 (even) then dc.w -> no error."""
        errs = self._lint_lines("Routine:\n    ds.b    4\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_accumulate_multiple_dc_b_to_odd_fires(self):
        """Two dc.b lines accumulating to odd -> E005 at dc.w."""
        errs = self._lint_lines("Routine:\n    dc.b    1, 2\n    dc.b    3\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 1)

    def test_accumulate_multiple_dc_b_to_even_ok(self):
        """Two dc.b lines accumulating to even -> no error."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.b    2\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_instruction_after_odd_bytes_fires(self):
        """68K instruction after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    nop\n")
        self.assertEqual(len(errs), 1)

    def test_dc_l_after_odd_bytes_fires(self):
        """dc.l after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    dc.l    $00000000\n")
        self.assertEqual(len(errs), 1)

    def test_ds_w_after_odd_bytes_fires(self):
        """ds.w after 1 dc.b byte -> E005."""
        errs = self._lint_lines("Routine:\n    dc.b    1\n    ds.w    1\n")
        self.assertEqual(len(errs), 1)

    def test_no_bytes_just_dc_w_ok(self):
        """dc.w with no preceding byte data -> no error."""
        errs = self._lint_lines("Routine:\n    dc.w    $0000\n")
        self.assertEqual(len(errs), 0)

    def test_string_dc_b_odd_fires(self):
        """dc.b "ABC" (3 bytes, odd) then dc.w -> E005."""
        errs = self._lint_lines('Routine:\n    dc.b    "ABC"\n    dc.w    $0000\n')
        self.assertEqual(len(errs), 1)

    def test_string_dc_b_even_ok(self):
        """dc.b "SEGA" (4 bytes, even) then dc.w -> no error."""
        errs = self._lint_lines('Routine:\n    dc.b    "SEGA"\n    dc.w    $0000\n')
        self.assertEqual(len(errs), 0)

    def test_dc_l_after_odd_ds_b_fires(self):
        """ds.b 1 (odd) then dc.l -> E005."""
        errs = self._lint_lines("Routine:\n    ds.b    1\n    dc.l    $00000000\n")
        self.assertEqual(len(errs), 1)

    def test_phase_block_skips_e005(self):
        """ds.b inside phase/dephase is RAM layout — E005 must not fire."""
        errs = self._lint_lines(
            "    phase $FFFF8000\n"
            "RAM_Start:\n"
            "    ds.b    19\n"
            "    ds.b    1\n"
            "    ds.l    1\n"
            "    dephase\n"
        )
        self.assertEqual(len(errs), 0)

    def test_after_dephase_e005_resumes(self):
        """E005 tracking resumes after dephase."""
        errs = self._lint_lines(
            "    phase $FFFF8000\n"
            "RAM_Start:\n"
            "    ds.b    1\n"
            "    dephase\n"
            "Routine:\n"
            "    dc.b    1\n"
            "    dc.w    $0000\n"
        )
        self.assertEqual(len(errs), 1)

    def test_nested_rept_suppresses_correctly(self):
        """Nested rept blocks must not unsuppress on inner endr."""
        errs = self._lint_lines(
            "Routine:\n"
            "    rept 4\n"
            "    rept 2\n"
            "    dc.b 1\n"
            "    endr\n"
            "    dc.b 1\n"       # still inside outer rept — should be suppressed
            "    dc.w $0000\n"   # would be E005 if not suppressed
            "    endr\n"
        )
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# Shared helper for multi-line lint tests (E006–E011)
# ---------------------------------------------------------------------------

def _lint_lines(lines_str, filepath="engine/test.asm"):
    """Process multi-line assembly string; return all Diagnostics."""
    ctx = LintContext(filepath, {})
    for i, line in enumerate(lines_str.strip().split("\n"), 1):
        t = tokenize_line(line)
        suppressed = _parse_suppressed(t.comment) if t.comment else set()
        run_checks(ctx, t, i, line, suppressed)
    return ctx.diagnostics


# ---------------------------------------------------------------------------
# E006: VDP write without Z80 stopped
# ---------------------------------------------------------------------------

class TestE006_VDPWithoutZ80(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E006"]

    def test_vdp_ctrl_write_without_stop_fires(self):
        """Direct write to (VDP_CTRL).l without stopZ80 -> E006."""
        code = """
Routine:
        move.l  #$40000000, (VDP_CTRL).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("VDP_CTRL", errs[0].message)

    def test_vdp_data_write_without_stop_fires(self):
        """Write to (VDP_DATA).l without stopZ80 -> E006."""
        code = """
Routine:
        move.l  d0, (VDP_DATA).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_vdp_ctrl_write_after_stop_clean(self):
        """Write to (VDP_CTRL).l after stopZ80 -> no E006."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_vdp_ctrl_read_without_stop_clean(self):
        """Reading VDP_CTRL (VDP status read) -> not a write -> no E006."""
        code = """
Routine:
        move.w  (VDP_CTRL).l, d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_vdp_hex_addr_write_without_stop_fires(self):
        """Write to ($C00004).l (literal VDP_CTRL address) without stop -> E006."""
        code = """
Routine:
        move.l  #$40000000, ($C00004).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_vdp_data_hex_addr_write_without_stop_fires(self):
        """Write to ($C00000).l (literal VDP_DATA address) without stop -> E006."""
        code = """
Routine:
        move.l  d0, ($C00000).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_setvdpreg_without_stop_no_e006_no_e008(self):
        """setVDPReg only writes shadow table RAM — no VDP hardware access.
        Neither E006 nor E008 should fire regardless of Z80 state."""
        code = """
Routine:
        setVDPReg vdp_mode2, #$34
        rts
"""
        diags = _lint_lines(code)
        e006 = [d for d in diags if d.code == "E006"]
        e008 = [d for d in diags if d.code == "E008"]
        self.assertEqual(len(e006), 0)
        self.assertEqual(len(e008), 0)


# ---------------------------------------------------------------------------
# E007: Unpaired stopZ80 / startZ80
# ---------------------------------------------------------------------------

class TestE007_UnpairedZ80(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E007"]

    def test_stop_without_start_before_rts_fires(self):
        """stopZ80 with no matching startZ80 before rts -> E007."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_paired_stop_start_clean(self):
        """Properly paired stopZ80/startZ80 before rts -> no E007."""
        code = """
Routine:
        stopZ80
        move.l  #$40000000, (VDP_CTRL).l
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_rts_without_stop_clean(self):
        """rts with Z80 never stopped -> no E007."""
        code = """
Routine:
        moveq   #0, d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E008: Macro contract violation (requires precondition not met)
# ---------------------------------------------------------------------------

class TestE008_MacroContract(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E008"]

    def test_startz80_without_prior_stop_fires(self):
        """startZ80 when Z80 not stopped -> E008."""
        code = """
Routine:
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("startZ80", errs[0].message)

    def test_setvdpreg_no_e008_regardless_of_z80_state(self):
        """setVDPReg writes shadow table RAM only — no VDP hardware access.
        No E008 should fire regardless of Z80 state."""
        code = """
Routine:
        setVDPReg vdp_mode2, #$34
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_setvdpreg_with_stop_also_clean(self):
        """setVDPReg after stopZ80 -> still no E008 (shadow table only)."""
        code = """
Routine:
        stopZ80
        setVDPReg vdp_mode2, #$34
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_enableints_without_disable_fires(self):
        """enableInts without prior disableInts -> E008."""
        code = """
Routine:
        enableInts
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("enableInts", errs[0].message)

    def test_enableints_with_disable_clean(self):
        """enableInts after disableInts -> no E008."""
        code = """
Routine:
        disableInts
        enableInts
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_queuestaticdma_no_requirement_clean(self):
        """queueStaticDMA has no requires -> no E008 regardless of state."""
        code = """
Routine:
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_startz80_after_stop_clean(self):
        """startZ80 after stopZ80 -> no E008."""
        code = """
Routine:
        stopZ80
        nop
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E011: Double stopZ80
# ---------------------------------------------------------------------------

class TestE011_DoubleStop(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E011"]

    def test_double_stopz80_fires(self):
        """Two consecutive stopZ80 calls -> E011 on the second."""
        code = """
Routine:
        stopZ80
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("stopZ80", errs[0].message)

    def test_single_stopz80_clean(self):
        """Single stopZ80 followed by startZ80 -> no E011."""
        code = """
Routine:
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_stop_start_stop_clean(self):
        """stopZ80 / startZ80 / stopZ80 is valid -> no E011."""
        code = """
Routine:
        stopZ80
        startZ80
        stopZ80
        startZ80
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# E009: SST access past bounds
# ---------------------------------------------------------------------------

class TestE009_SSTBounds(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E009"]

    # --- should NOT fire ---

    def test_valid_sst_field_access_no_error(self):
        """SST_x_pos (offset $02) in operand -> no E009."""
        code = """
Routine:
        move.l  SST_x_pos(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_sst_custom_base_no_error(self):
        """SST_sst_custom ($32) with no addition -> offset $32 < $50 -> no E009."""
        code = """
Routine:
        move.b  SST_sst_custom(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_sst_custom_plus_28_no_error(self):
        """SST_sst_custom+28 = $32+$1C = $4E < $50 -> no E009."""
        code = """
Routine:
        move.b  SST_sst_custom+28(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_non_sst_offset_no_error(self):
        """Non-SST symbol in operand -> no E009."""
        code = """
Routine:
        move.b  some_other_field(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_equ_sst_custom_in_range_no_error(self):
        """Assignment _foo = SST_sst_custom+4 ($36 < $50) -> no E009."""
        code = """
_foo = SST_sst_custom+4
Routine:
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    # --- should fire ---

    def test_sst_custom_plus_30_fires(self):
        """SST_sst_custom+30 = $32+$1E = $50 = SST_len -> out of bounds, E009."""
        code = """
Routine:
        move.b  SST_sst_custom+30(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("E009", errs[0].code)

    def test_sst_custom_plus_40_fires(self):
        """SST_sst_custom+40 = $32+$28 = $5A -> way out of bounds, E009."""
        code = """
Routine:
        move.b  SST_sst_custom+40(a0), d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)

    def test_equ_definition_out_of_range_fires(self):
        """_bad_field = SST_sst_custom+32 ($32+$20=$52 >= $50) -> E009."""
        code = """
_bad_field = SST_sst_custom+32
Routine:
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("E009", errs[0].code)


# ---------------------------------------------------------------------------
# E010: SR save/restore mismatch
# ---------------------------------------------------------------------------

class TestE010_SRMismatch(unittest.TestCase):

    def _errs(self, lines_str, filepath="engine/test.asm"):
        return [d for d in _lint_lines(lines_str, filepath) if d.code == "E010"]

    def test_sr_save_no_restore_rts_fires(self):
        """move.w sr, -(sp) with no restore before rts -> E010."""
        code = """
Routine:
        move.w  sr, -(sp)
        nop
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 1)
        self.assertIn("E010", errs[0].code)

    def test_sr_save_restore_rts_clean(self):
        """move.w sr, -(sp) then move.w (sp)+, sr then rts -> no E010."""
        code = """
Routine:
        move.w  sr, -(sp)
        nop
        move.w  (sp)+, sr
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)

    def test_no_sr_save_rts_clean(self):
        """rts without any SR save -> no E010."""
        code = """
Routine:
        moveq   #0, d0
        rts
"""
        errs = self._errs(code)
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# Helper for warning tests
# ---------------------------------------------------------------------------

def _lint(line, filepath="engine/test.asm"):
    """Lint a single line; return all Diagnostics."""
    ctx = LintContext(filepath, {})
    t = tokenize_line(line)
    suppressed = _parse_suppressed(t.comment) if t.comment else set()
    run_checks(ctx, t, 1, line, suppressed)
    return ctx.diagnostics


def _lint_lines_w(lines_str, filepath="engine/test.asm"):
    """Process multi-line assembly string; return all Diagnostics (including warnings)."""
    ctx = LintContext(filepath, {})
    for i, line in enumerate(lines_str.strip().split("\n"), 1):
        t = tokenize_line(line)
        suppressed = _parse_suppressed(t.comment) if t.comment else set()
        run_checks(ctx, t, i, line, suppressed)
    return ctx.diagnostics


# ---------------------------------------------------------------------------
# W001: clr on memory (read-modify-write)
# ---------------------------------------------------------------------------

class TestW001_ClrOnMemory(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W001"]

    def test_clr_w_memory_warns(self):
        warns = self._warns("    clr.w   ($FF0000).l")
        self.assertEqual(len(warns), 1)
        self.assertIn("clr", warns[0].message)

    def test_clr_l_memory_warns(self):
        warns = self._warns("    clr.l   (a0)")
        self.assertEqual(len(warns), 1)

    def test_clr_w_memory_indirect_warns(self):
        warns = self._warns("    clr.w   (a1)+")
        self.assertEqual(len(warns), 1)

    def test_clr_w_register_ok(self):
        warns = self._warns("    clr.w   d0")
        self.assertEqual(len(warns), 0)

    def test_clr_l_register_ok(self):
        warns = self._warns("    clr.l   d3")
        self.assertEqual(len(warns), 0)

    def test_clr_b_memory_ok(self):
        """clr.b on memory is not checked (less problematic)."""
        warns = self._warns("    clr.b   (a0)")
        self.assertEqual(len(warns), 0)

    def test_clr_w_suppressed(self):
        warns = [d for d in _lint("    clr.w   (a0)  ; lint: disable=W001")
                 if d.code == "W001"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W002: cmp #0 instead of tst
# ---------------------------------------------------------------------------

class TestW002_CmpZero(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W002"]

    def test_cmp_w_zero_warns(self):
        warns = self._warns("    cmp.w   #0, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("tst", warns[0].message)

    def test_cmp_l_zero_warns(self):
        warns = self._warns("    cmp.l   #0, d1")
        self.assertEqual(len(warns), 1)

    def test_cmpi_w_zero_warns(self):
        warns = self._warns("    cmpi.w  #0, d0")
        self.assertEqual(len(warns), 1)

    def test_cmpi_b_zero_warns(self):
        warns = self._warns("    cmpi.b  #0, d0")
        self.assertEqual(len(warns), 1)

    def test_cmp_nonzero_ok(self):
        warns = self._warns("    cmp.w   #1, d0")
        self.assertEqual(len(warns), 0)

    def test_cmp_negative_ok(self):
        warns = self._warns("    cmp.w   #-1, d0")
        self.assertEqual(len(warns), 0)

    def test_tst_ok(self):
        warns = self._warns("    tst.w   d0")
        self.assertEqual(len(warns), 0)

    def test_cmp_zero_suppressed(self):
        warns = [d for d in _lint("    cmp.w   #0, d0  ; lint: disable=W002")
                 if d.code == "W002"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W003: move.w #0 to dreg instead of moveq
# ---------------------------------------------------------------------------

class TestW003_MoveWZero(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W003"]

    def test_move_w_zero_to_dreg_warns(self):
        warns = self._warns("    move.w  #0, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("moveq", warns[0].message)

    def test_move_w_zero_to_d7_warns(self):
        warns = self._warns("    move.w  #0, d7")
        self.assertEqual(len(warns), 1)

    def test_move_w_zero_to_memory_ok(self):
        warns = self._warns("    move.w  #0, (a0)")
        self.assertEqual(len(warns), 0)

    def test_move_l_zero_to_dreg_not_w003(self):
        """W003 only checks move.w #0. move.l #0 to dreg is caught by W013."""
        warns = self._warns("    move.l  #0, d0")
        self.assertEqual(len(warns), 0)

    def test_moveq_zero_ok(self):
        warns = self._warns("    moveq   #0, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_nonzero_ok(self):
        warns = self._warns("    move.w  #1, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_zero_to_dreg_suppressed(self):
        warns = [d for d in _lint("    move.w  #0, d0  ; lint: disable=W003")
                 if d.code == "W003"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W004: add/sub #1-8 instead of addq/subq
# ---------------------------------------------------------------------------

class TestW004_AddSubQ(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W004"]

    def test_add_w_one_warns(self):
        warns = self._warns("    add.w   #1, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("addq", warns[0].message)

    def test_sub_l_eight_warns(self):
        warns = self._warns("    sub.l   #8, a0")
        self.assertEqual(len(warns), 1)

    def test_addi_w_four_warns(self):
        warns = self._warns("    addi.w  #4, d0")
        self.assertEqual(len(warns), 1)

    def test_subi_b_three_warns(self):
        warns = self._warns("    subi.b  #3, d1")
        self.assertEqual(len(warns), 1)

    def test_add_w_nine_ok(self):
        warns = self._warns("    add.w   #9, d0")
        self.assertEqual(len(warns), 0)

    def test_sub_zero_ok(self):
        warns = self._warns("    sub.w   #0, d0")
        self.assertEqual(len(warns), 0)

    def test_addq_ok(self):
        warns = self._warns("    addq.w  #1, d0")
        self.assertEqual(len(warns), 0)

    def test_subq_ok(self):
        warns = self._warns("    subq.w  #8, d0")
        self.assertEqual(len(warns), 0)

    def test_add_w_one_suppressed(self):
        warns = [d for d in _lint("    add.w   #1, d0  ; lint: disable=W004")
                 if d.code == "W004"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W005: long branch to local label
# ---------------------------------------------------------------------------

class TestW005_LongBranchLocal(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W005"]

    def test_bra_w_local_warns(self):
        warns = self._warns("    bra.w   .loop")
        self.assertEqual(len(warns), 1)
        self.assertIn(".s", warns[0].message)

    def test_beq_w_local_warns(self):
        warns = self._warns("    beq.w   .done")
        self.assertEqual(len(warns), 1)

    def test_bne_w_local_warns(self):
        warns = self._warns("    bne.w   .retry")
        self.assertEqual(len(warns), 1)

    def test_bra_w_global_ok(self):
        warns = self._warns("    bra.w   GlobalLabel")
        self.assertEqual(len(warns), 0)

    def test_bra_s_local_ok(self):
        warns = self._warns("    bra.s   .loop")
        self.assertEqual(len(warns), 0)

    def test_bra_s_global_ok(self):
        warns = self._warns("    bra.s   GlobalLabel")
        self.assertEqual(len(warns), 0)

    def test_bra_w_local_suppressed(self):
        warns = [d for d in _lint("    bra.w   .loop  ; lint: disable=W005")
                 if d.code == "W005"]
        self.assertEqual(len(warns), 0)

    def test_message_includes_verify_note(self):
        warns = self._warns("    bra.w   .loop")
        self.assertIn("verify distance", warns[0].message)


# ---------------------------------------------------------------------------
# W006: routine missing header comment
# ---------------------------------------------------------------------------

class TestW006_MissingHeader(unittest.TestCase):

    def _warns(self, lines_str):
        return [d for d in _lint_lines_w(lines_str) if d.code == "W006"]

    def test_no_header_warns(self):
        code = "\n; some unrelated comment\nMyRoutine:\n    moveq   #0, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 1)
        self.assertIn("MyRoutine", warns[0].message)

    def test_with_in_comment_ok(self):
        code = "\n; In: d0 = value\nMyRoutine:\n    moveq   #0, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_with_out_comment_ok(self):
        code = "\n; Out: d0 = result\nMyRoutine:\n    moveq   #0, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_with_clobbers_comment_ok(self):
        code = "\n; Clobbers: d0-d2\nMyRoutine:\n    moveq   #0, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_with_divider_ok(self):
        code = "\n; -------\nMyRoutine:\n    moveq   #0, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_data_label_ok(self):
        """Labels followed by dc.* are data, not routines -- skip W006."""
        code = "\nMyData:\n    dc.w    $0000\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_binclude_label_ok(self):
        """Labels followed by BINCLUDE are data -- skip W006."""
        code = '\nMyBinData:\n    BINCLUDE "data/foo.bin"\n'
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_local_label_not_checked(self):
        """Local labels (.dot) are never checked for W006."""
        code = "\n; In: d0\nMyRoutine:\n    moveq   #0, d0\n.loop:\n    dbf     d0, .loop\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_second_routine_no_header_warns(self):
        """First routine has header, second doesnt -- only second warns."""
        code = "\n; In: d0\nFirstRoutine:\n    rts\n\nSecondRoutine:\n    moveq   #1, d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 1)
        self.assertIn("SecondRoutine", warns[0].message)

    def test_phase_block_label_ok(self):
        """Labels inside phase/dephase blocks are RAM addresses, not routines."""
        code = "\n    phase   $FFFF8000\nRAM_Start:\n    ds.b    $100\nRAM_End:\n    dephase\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_dephase_label_ok(self):
        """Label followed by dephase is an end marker, not a routine."""
        code = "\n    phase   $FFFF8000\nSomeData:\n    ds.b    $10\nSomeEnd:\n    dephase\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W007: lsl #1 instead of add dn, dn
# ---------------------------------------------------------------------------

class TestW007_LslOne(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W007"]

    def test_lsl_w_one_warns(self):
        warns = self._warns("    lsl.w   #1, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("add", warns[0].message)

    def test_lsl_l_one_warns(self):
        warns = self._warns("    lsl.l   #1, d3")
        self.assertEqual(len(warns), 1)

    def test_lsl_b_one_warns(self):
        warns = self._warns("    lsl.b   #1, d1")
        self.assertEqual(len(warns), 1)

    def test_lsl_two_ok(self):
        warns = self._warns("    lsl.w   #2, d0")
        self.assertEqual(len(warns), 0)

    def test_lsr_one_ok(self):
        """lsr is right shift -- different semantics, dont flag."""
        warns = self._warns("    lsr.w   #1, d0")
        self.assertEqual(len(warns), 0)

    def test_asl_one_ok(self):
        """asl -- not lsl, dont flag."""
        warns = self._warns("    asl.w   #1, d0")
        self.assertEqual(len(warns), 0)

    def test_lsl_one_suppressed(self):
        warns = [d for d in _lint("    lsl.w   #1, d0  ; lint: disable=W007")
                 if d.code == "W007"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W008: sub dn, dn to zero
# ---------------------------------------------------------------------------

class TestW008_SubSelf(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W008"]

    def test_sub_w_same_reg_warns(self):
        warns = self._warns("    sub.w   d0, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("moveq", warns[0].message)

    def test_sub_l_same_reg_warns(self):
        warns = self._warns("    sub.l   d3, d3")
        self.assertEqual(len(warns), 1)

    def test_sub_b_same_reg_warns(self):
        warns = self._warns("    sub.b   d1, d1")
        self.assertEqual(len(warns), 1)

    def test_sub_different_regs_ok(self):
        warns = self._warns("    sub.w   d1, d0")
        self.assertEqual(len(warns), 0)

    def test_sub_w_same_reg_suppressed(self):
        warns = [d for d in _lint("    sub.w   d0, d0  ; lint: disable=W008")
                 if d.code == "W008"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W009: swap + clr.w on same register
# ---------------------------------------------------------------------------

class TestW009_Removed(unittest.TestCase):
    """W009 was removed — swap+clr.w is a 16.16 fixed-point pattern, not redundant."""

    def _warns(self, lines_str):
        return [d for d in _lint_lines_w(lines_str) if d.code == "W009"]

    def test_swap_then_clr_w_no_longer_warns(self):
        code = "\nRoutine:\n    swap    d0\n    clr.w   d0\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W010: indexed addressing in dbf loop
# ---------------------------------------------------------------------------

class TestW010_IndexedInLoop(unittest.TestCase):

    def _warns(self, lines_str):
        return [d for d in _lint_lines_w(lines_str) if d.code == "W010"]

    def test_indexed_in_loop_warns(self):
        code = "\nRoutine:\n.loop:\n    move.w  (a0,d1.w), d2\n    dbf     d0, .loop\n    rts\n"
        warns = self._warns(code)
        self.assertGreater(len(warns), 0)
        self.assertIn("loop-invariant", warns[0].message)

    def test_indexed_outside_loop_ok(self):
        code = "\nRoutine:\n    move.w  (a0,d1.w), d2\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)

    def test_simple_addressing_in_loop_ok(self):
        code = "\nRoutine:\n.loop:\n    move.w  (a0)+, d2\n    dbf     d0, .loop\n    rts\n"
        warns = self._warns(code)
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W011: movem with single register
# ---------------------------------------------------------------------------

class TestW011_MovemSingle(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W011"]

    def test_movem_single_push_warns(self):
        warns = self._warns("    movem.l d0, -(sp)")
        self.assertEqual(len(warns), 1)
        self.assertIn("move", warns[0].message)

    def test_movem_single_pop_warns(self):
        warns = self._warns("    movem.l (sp)+, d0")
        self.assertEqual(len(warns), 1)

    def test_movem_single_areg_warns(self):
        warns = self._warns("    movem.l a0, -(sp)")
        self.assertEqual(len(warns), 1)

    def test_movem_range_ok(self):
        warns = self._warns("    movem.l d0-d3, -(sp)")
        self.assertEqual(len(warns), 0)

    def test_movem_list_ok(self):
        warns = self._warns("    movem.l d0/a0, -(sp)")
        self.assertEqual(len(warns), 0)

    def test_movem_multi_range_ok(self):
        warns = self._warns("    movem.l d0-d2/a1-a3, -(sp)")
        self.assertEqual(len(warns), 0)

    def test_movem_single_suppressed(self):
        warns = [d for d in _lint("    movem.l d0, -(sp)  ; lint: disable=W011")
                 if d.code == "W011"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W012: move.l to address register instead of movea.l
# ---------------------------------------------------------------------------

class TestW012_MoveToAreg(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W012"]

    def test_move_l_to_a0_warns(self):
        warns = self._warns("    move.l  d0, a0")
        self.assertEqual(len(warns), 1)
        self.assertIn("movea.l", warns[0].message)

    def test_move_l_to_a5_warns(self):
        warns = self._warns("    move.l  (a1), a5")
        self.assertEqual(len(warns), 1)

    def test_movea_l_ok(self):
        warns = self._warns("    movea.l d0, a0")
        self.assertEqual(len(warns), 0)

    def test_move_l_to_dreg_ok(self):
        warns = self._warns("    move.l  d1, d0")
        self.assertEqual(len(warns), 0)

    def test_move_l_to_memory_ok(self):
        warns = self._warns("    move.l  d0, (a0)")
        self.assertEqual(len(warns), 0)

    def test_move_w_to_areg_ok(self):
        """W012 only checks .l moves."""
        warns = self._warns("    move.w  d0, a0")
        self.assertEqual(len(warns), 0)

    def test_move_l_to_areg_suppressed(self):
        warns = [d for d in _lint("    move.l  d0, a0  ; lint: disable=W012")
                 if d.code == "W012"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# W013: move.w/move.l #N in moveq range to data register
# ---------------------------------------------------------------------------

class TestW013_MoveInMoveqRange(unittest.TestCase):

    def _warns(self, line):
        return [d for d in _lint(line) if d.code == "W013"]

    def test_move_w_small_positive_to_dreg_warns(self):
        warns = self._warns("    move.w  #$10, d0")
        self.assertEqual(len(warns), 1)
        self.assertIn("moveq", warns[0].message)

    def test_move_w_negative_in_range_to_dreg_warns(self):
        warns = self._warns("    move.w  #-1, d0")
        self.assertEqual(len(warns), 1)

    def test_move_l_small_to_dreg_warns(self):
        warns = self._warns("    move.l  #$7F, d0")
        self.assertEqual(len(warns), 1)

    def test_move_w_zero_not_w013(self):
        """#0 is caught by W003, not W013."""
        warns = self._warns("    move.w  #0, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_out_of_range_ok(self):
        warns = self._warns("    move.w  #$100, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_neg_out_of_range_ok(self):
        warns = self._warns("    move.w  #-129, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_to_memory_ok(self):
        warns = self._warns("    move.w  #$10, (a0)")
        self.assertEqual(len(warns), 0)

    def test_move_w_to_areg_ok(self):
        """move.w/l #N to address register is not flagged by W013."""
        warns = self._warns("    move.w  #$10, a0")
        self.assertEqual(len(warns), 0)

    def test_moveq_ok(self):
        warns = self._warns("    moveq   #$10, d0")
        self.assertEqual(len(warns), 0)

    def test_move_w_small_suppressed(self):
        warns = [d for d in _lint("    move.w  #$10, d0  ; lint: disable=W013")
                 if d.code == "W013"]
        self.assertEqual(len(warns), 0)


# ---------------------------------------------------------------------------
# End-to-end tests against the real codebase
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    def test_lint_main_no_crash(self):
        """Linting main.asm should not crash."""
        from tools.s4lint import discover_files, lint_file
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_path = os.path.join(base, "main.asm")
        if not os.path.isfile(main_path):
            self.skipTest("main.asm not found")
        files = discover_files(main_path)
        self.assertGreater(len(files), 5)
        for fp in files:
            ctx = lint_file(fp, {}, base)
            self.assertIsInstance(ctx.diagnostics, list)

    def test_cli_exit_code(self):
        """CLI with --no-warnings should return 0 on clean codebase."""
        import subprocess, os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_path = os.path.join(base, "main.asm")
        if not os.path.isfile(main_path):
            self.skipTest("main.asm not found")
        result = subprocess.run(
            ["python3", os.path.join(base, "tools", "s4lint.py"),
             "--no-warnings", main_path],
            capture_output=True, text=True, cwd=base
        )
        self.assertIn(result.returncode, (0, 1))


# ---------------------------------------------------------------------------
# W015: Global label not PascalCase
# ---------------------------------------------------------------------------

class TestW015_PascalCase(unittest.TestCase):

    def _errs(self, lines_str):
        return [d for d in _lint_lines(lines_str) if d.code == "W015"]

    # --- Clean cases (should NOT warn) ---

    def test_pascal_case_simple(self):
        """PascalCase label — no W015."""
        self.assertEqual(len(self._errs("EntryPoint:\n    rts\n")), 0)

    def test_pascal_case_with_underscore_segment(self):
        """PascalCase_Segment style is valid."""
        self.assertEqual(len(self._errs("Camera_X:\n    rts\n")), 0)

    def test_pascal_case_vdp_init(self):
        """VDP_Init is valid PascalCase."""
        self.assertEqual(len(self._errs("VDP_Init:\n    rts\n")), 0)

    def test_pascal_case_dma_queue_process(self):
        """DMA_Queue_Process is valid PascalCase."""
        self.assertEqual(len(self._errs("DMA_Queue_Process:\n    rts\n")), 0)

    def test_pascal_case_ram_start(self):
        """RAM_Start is valid PascalCase."""
        self.assertEqual(len(self._errs("RAM_Start:\n    rts\n")), 0)

    def test_single_char_label_skipped(self):
        """Single-character labels are exempt from W015."""
        self.assertEqual(len(self._errs("X:\n    rts\n")), 0)

    def test_constant_with_equals_skipped(self):
        """Constants defined via = are W016 territory, not W015."""
        errs = self._errs("max_objects = 40\n")
        self.assertEqual(len(errs), 0)

    def test_constant_with_equ_skipped(self):
        """Constants defined via equ are W016 territory, not W015."""
        errs = self._errs("vdp_data equ $C00000\n")
        self.assertEqual(len(errs), 0)

    def test_struct_definition_skipped(self):
        """struct definitions are exempt from W015."""
        errs = self._errs("my_struct struct\nendstruct\n")
        self.assertEqual(len(errs), 0)

    def test_macro_definition_skipped(self):
        """macro definitions are exempt from W015."""
        errs = self._errs("my_macro macro\nendm\n")
        self.assertEqual(len(errs), 0)

    def test_function_definition_skipped(self):
        """function definitions are exempt from W015."""
        errs = self._errs("vram_bytes function x, x*32\n")
        self.assertEqual(len(errs), 0)

    # --- Warning cases ---

    def test_lowercase_start_warns(self):
        """Label starting with lowercase triggers W015."""
        errs = self._errs("vdp_init:\n    rts\n")
        self.assertEqual(len(errs), 1)
        self.assertIn("vdp_init", errs[0].message)

    def test_all_caps_label_passes(self):
        """ALL_CAPS label (not a constant) matches the PascalCase regex — no W015.
        Uppercase letters satisfy [A-Za-z0-9]*, so DMA_QUEUE_ADD is accepted."""
        errs = self._errs("DMA_QUEUE_ADD:\n    rts\n")
        self.assertEqual(len(errs), 0)

    def test_camel_case_warns(self):
        """camelCase label triggers W015."""
        errs = self._errs("myRoutine:\n    rts\n")
        self.assertEqual(len(errs), 1)
        self.assertIn("myRoutine", errs[0].message)

    def test_suppression_works(self):
        """W015 can be suppressed with ; lint: disable=W015."""
        errs = self._errs("vdp_init: ; lint: disable=W015\n    rts\n")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# W016: Constant not ALL_CAPS
# ---------------------------------------------------------------------------

class TestW016_AllCaps(unittest.TestCase):

    def _errs(self, lines_str):
        return [d for d in _lint_lines(lines_str) if d.code == "W016"]

    # --- Clean cases (should NOT warn) ---

    def test_all_caps_equals(self):
        """ALL_CAPS constant with = — no W016."""
        self.assertEqual(len(self._errs("MAX_OBJECTS = 40\n")), 0)

    def test_all_caps_equ(self):
        """ALL_CAPS constant with equ — no W016."""
        self.assertEqual(len(self._errs("VDP_DATA equ $C00000\n")), 0)

    def test_single_char_constant(self):
        """Single-char constant N = 5 — no W016 (single-char uppercase satisfies regex)."""
        self.assertEqual(len(self._errs("N = 5\n")), 0)

    def test_all_caps_with_numbers(self):
        """ALL_CAPS_1 style is valid."""
        self.assertEqual(len(self._errs("VRAM_POOL_SIZE = $600\n")), 0)

    # --- Warning cases ---

    def test_mixed_case_warns(self):
        """Mixed-case constant triggers W016."""
        errs = self._errs("Vram_Pool = $1000\n")
        self.assertEqual(len(errs), 1)
        self.assertIn("Vram_Pool", errs[0].message)

    def test_camel_case_warns(self):
        """camelCase constant triggers W016."""
        errs = self._errs("maxObjects = 40\n")
        self.assertEqual(len(errs), 1)
        self.assertIn("maxObjects", errs[0].message)

    def test_lowercase_equ_warns(self):
        """lowercase equ constant triggers W016."""
        errs = self._errs("vdp_data equ $C00000\n")
        self.assertEqual(len(errs), 1)
        self.assertIn("vdp_data", errs[0].message)

    def test_suppression_works(self):
        """W016 can be suppressed with ; lint: disable=W016."""
        errs = self._errs("vdp_data equ $C00000 ; lint: disable=W016\n")
        self.assertEqual(len(errs), 0)

    def test_underscore_prefix_skipped(self):
        """SST custom overlays use _lowercase convention — W016 skips them."""
        for line in ("_dplc_ptr = SST_sst_custom+0", "_art_base = SST_sst_custom+4"):
            errs = self._errs(f"{line}\n")
            self.assertEqual(len(errs), 0, f"'{line}' should be skipped (SST overlay)")


# ---------------------------------------------------------------------------
# W017: Local label not .lowercase
# ---------------------------------------------------------------------------

class TestW017_LocalLabel(unittest.TestCase):

    def _errs(self, lines_str):
        return [d for d in _lint_lines(lines_str) if d.code == "W017"]

    # --- Clean cases (should NOT warn) ---

    def test_lowercase_loop(self):
        """'.loop' is valid — no W017."""
        self.assertEqual(len(self._errs("Routine:\n.loop:\n    rts\n")), 0)

    def test_lowercase_done(self):
        """'.done' is valid — no W017."""
        self.assertEqual(len(self._errs("Routine:\n.done:\n    rts\n")), 0)

    def test_lowercase_with_underscores(self):
        """'.not_found' with underscores is valid — no W017."""
        self.assertEqual(len(self._errs("Routine:\n.not_found:\n    rts\n")), 0)

    def test_lowercase_with_digits(self):
        """'.skip_pal' is valid — no W017."""
        self.assertEqual(len(self._errs("Routine:\n.skip_pal:\n    rts\n")), 0)

    # --- Warning cases ---

    def test_uppercase_start_warns(self):
        """'.Loop' (capital start) triggers W017."""
        errs = self._errs("Routine:\n.Loop:\n    rts\n")
        self.assertEqual(len(errs), 1)
        self.assertIn(".Loop", errs[0].message)

    def test_all_caps_warns(self):
        """'.DONE' triggers W017."""
        errs = self._errs("Routine:\n.DONE:\n    rts\n")
        self.assertEqual(len(errs), 1)
        self.assertIn(".DONE", errs[0].message)

    def test_camel_case_warns(self):
        """'.notFound' (camelCase) triggers W017."""
        errs = self._errs("Routine:\n.notFound:\n    rts\n")
        self.assertEqual(len(errs), 1)
        self.assertIn(".notFound", errs[0].message)

    def test_suppression_works(self):
        """W017 can be suppressed with ; lint: disable=W017."""
        errs = self._errs("Routine:\n.Loop: ; lint: disable=W017\n    rts\n")
        self.assertEqual(len(errs), 0)


# ---------------------------------------------------------------------------
# W018: Routine too long
# ---------------------------------------------------------------------------

class TestW018_RoutineLength(unittest.TestCase):

    def _warnings(self, lines_str, filepath="engine/test.asm"):
        diags = _lint_lines(lines_str, filepath)
        return [d for d in diags if d.code == "W018"]

    def _make_routine(self, name, instruction_count):
        """Build a multi-line routine with N nop instructions + rts."""
        lines = [f"{name}:"]
        for _ in range(instruction_count):
            lines.append("    nop")
        lines.append("    rts")
        return "\n".join(lines) + "\n"

    def test_short_routine_ok(self):
        w = self._warnings(self._make_routine("Short_Routine", 50))
        self.assertEqual(len(w), 0)

    def test_exactly_100_ok(self):
        """100 instructions is at the threshold — should not warn.
        99 nops + 1 rts = 100 instructions."""
        w = self._warnings(self._make_routine("Threshold_Routine", 99))
        self.assertEqual(len(w), 0)

    def test_101_warns(self):
        """101 instructions exceeds threshold — should warn.
        100 nops + 1 rts = 101 instructions."""
        w = self._warnings(self._make_routine("Long_Routine", 100))
        self.assertEqual(len(w), 1)
        self.assertIn("Long_Routine", w[0].message)
        self.assertIn("101", w[0].message)
        self.assertIn("hot-path", w[0].message)

    def test_suppressed(self):
        lines = "Long_Routine:\n" + "    nop\n" * 110 + "    rts ; lint: disable=W018\n"
        w = self._warnings(lines)
        self.assertEqual(len(w), 0)

    def test_bra_does_not_fire(self):
        """Routines ending with bra (tail call) don't fire W018."""
        lines = "Long_Routine:\n" + "    nop\n" * 110 + "    bra.w Other_Routine\n"
        w = self._warnings(lines)
        self.assertEqual(len(w), 0)


# ---------------------------------------------------------------------------
# W019: File missing header comment
# ---------------------------------------------------------------------------

class TestW019_FileHeader(unittest.TestCase):

    def _lint_content(self, content, filename="test.asm"):
        """Write content to a temp file, lint it, return W019 diagnostics."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".asm", delete=False) as f:
            f.write(content)
            f.flush()
            ctx = lint_file(f.name, {}, os.path.dirname(f.name))
        os.unlink(f.name)
        return [d for d in ctx.diagnostics if d.code == "W019"]

    def test_comment_first_line_ok(self):
        w = self._lint_content("; Boot sequence\nEntryPoint:\n    rts\n")
        self.assertEqual(len(w), 0)

    def test_blank_then_comment_ok(self):
        """Blank lines before the header comment are fine."""
        w = self._lint_content("\n\n; Boot sequence\nEntryPoint:\n    rts\n")
        self.assertEqual(len(w), 0)

    def test_code_first_warns(self):
        w = self._lint_content("EntryPoint:\n    rts\n")
        self.assertEqual(len(w), 1)

    def test_empty_file_warns(self):
        w = self._lint_content("")
        self.assertEqual(len(w), 1)

    def test_whitespace_only_warns(self):
        w = self._lint_content("   \n   \n")
        self.assertEqual(len(w), 1)

    def test_indented_comment_ok(self):
        """Comments with leading whitespace still count."""
        w = self._lint_content("    ; indented header\nRoutine:\n    rts\n")
        self.assertEqual(len(w), 0)


# ---------------------------------------------------------------------------
# Diagnostic summary footer
# ---------------------------------------------------------------------------

class TestSummaryFooter(unittest.TestCase):

    def _run_lint(self, content, extra_args=None):
        """Write content to temp file, run main(), return (exit_code, stderr)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".asm", delete=False) as f:
            f.write(content)
            f.flush()
            fname = f.name
        try:
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = s4lint_main(["--no-follow-includes"] + (extra_args or []) + [fname])
            return code, buf.getvalue()
        finally:
            os.unlink(fname)

    def test_summary_with_warnings(self):
        """Summary line appears after diagnostics."""
        _, stderr = self._run_lint("; header\nvdp_init:\n    rts\n")
        self.assertIn("s4lint:", stderr)
        self.assertIn("warning", stderr.split("s4lint:")[-1])

    def test_summary_no_issues(self):
        """Clean file shows 'no issues found'."""
        _, stderr = self._run_lint(
            "; header\n; -------\nClean_Routine:\n    rts\n",
            extra_args=["--skip=W006,W018"],
        )
        self.assertIn("no issues found", stderr)

    def test_summary_counts_by_code(self):
        """Per-code breakdown shows the code."""
        _, stderr = self._run_lint("; header\nvdp_init:\n    rts\nbad_func:\n    rts\n")
        summary = stderr.split("s4lint:")[-1]
        self.assertIn("W015", summary)

    def test_summary_respects_no_warnings(self):
        """--no-warnings suppresses warning counts in summary."""
        _, stderr = self._run_lint(
            "; header\nvdp_init:\n    rts\n",
            extra_args=["--no-warnings", "--skip=W006,W018"],
        )
        self.assertIn("no issues found", stderr)

    def test_summary_shows_label(self):
        """Human-readable label appears next to code."""
        _, stderr = self._run_lint("; header\nvdp_init:\n    rts\n")
        self.assertIn("global label not PascalCase", stderr)

    def test_summary_warnings_as_errors(self):
        """--warnings-as-errors promotes warning counts to error counts in summary."""
        code, stderr = self._run_lint(
            "; header\nvdp_init:\n    rts\n",
            extra_args=["--warnings-as-errors"],
        )
        summary_line = [l for l in stderr.splitlines() if l.startswith("s4lint:")][0]
        self.assertIn("error", summary_line)
        self.assertNotIn("warning", summary_line)
        self.assertEqual(code, 1)


class TestSeverityClassification(unittest.TestCase):

    def _lint(self, content, extra_args=None):
        """Write content to temp file, run lint, return diagnostics list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".asm", delete=False) as f:
            f.write(content)
            f.flush()
            fname = f.name
        try:
            ctx = lint_file(fname, {
                "no_warnings": False,
                "warnings_as_errors": False,
                "no_suggestions": False,
            }, os.path.dirname(fname))
            return ctx.diagnostics
        finally:
            os.unlink(fname)

    def test_w005_is_suggestion(self):
        """W005 (branch should use .s) should have severity 'suggestion'."""
        diags = self._lint("; header\n; ---\nMyRoutine:\n    bne.w .foo\n.foo:\n    rts\n")
        w005 = [d for d in diags if d.code == "W005"]
        self.assertTrue(len(w005) > 0, "Expected at least one W005")
        self.assertEqual(w005[0].severity, "suggestion")

    def test_w006_is_suggestion(self):
        """W006 (missing header comment) should have severity 'suggestion'."""
        diags = self._lint("; header\nMyRoutine:\n    rts\n")
        w006 = [d for d in diags if d.code == "W006"]
        self.assertTrue(len(w006) > 0, "Expected at least one W006")
        self.assertEqual(w006[0].severity, "suggestion")

    def test_w010_is_suggestion(self):
        """W010 (indexed addressing in loop) should have severity 'suggestion'."""
        diags = self._lint(
            "; header\n; ---\nMyRoutine:\n"
            ".loop:\n    move.w (a0,d0.w), d1\n    dbf d2, .loop\n    rts\n"
        )
        w010 = [d for d in diags if d.code == "W010"]
        self.assertTrue(len(w010) > 0, "Expected at least one W010")
        self.assertEqual(w010[0].severity, "suggestion")

    def test_w018_is_suggestion(self):
        """W018 (routine too long) should have severity 'suggestion'."""
        diags = self._lint("; header\n; ---\nLongRoutine:\n" + "    nop\n" * 101 + "    rts\n")
        w018 = [d for d in diags if d.code == "W018"]
        self.assertTrue(len(w018) > 0, "Expected at least one W018")
        self.assertEqual(w018[0].severity, "suggestion")

    def test_w001_stays_warning(self):
        """W001 (clr on memory) should remain severity 'warning'."""
        diags = self._lint("; header\n; ---\nMyRoutine:\n    clr.w (a0)\n    rts\n")
        w001 = [d for d in diags if d.code == "W001"]
        self.assertTrue(len(w001) > 0, "Expected at least one W001")
        self.assertEqual(w001[0].severity, "warning")

    def test_severity_dict_has_four_entries(self):
        """DIAGNOSTIC_SEVERITY should classify exactly W005, W006, W010, W018."""
        self.assertEqual(set(DIAGNOSTIC_SEVERITY.keys()), {"W005", "W006", "W010", "W018"})
        for code in DIAGNOSTIC_SEVERITY:
            self.assertEqual(DIAGNOSTIC_SEVERITY[code], "suggestion")


class TestSeverityOutput(unittest.TestCase):

    def _run(self, content, extra_args=None):
        """Write content to temp file, run main(), return (exit_code, stderr)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".asm", delete=False) as f:
            f.write(content)
            f.flush()
            fname = f.name
        try:
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = s4lint_main(["--no-follow-includes"] + (extra_args or []) + [fname])
            return code, buf.getvalue()
        finally:
            os.unlink(fname)

    def test_suggestion_line_format(self):
        """Suggestion diagnostics print 'suggestion:' not 'warning:'."""
        _, stderr = self._run("; header\n; ---\nMyRoutine:\n    bne.w .foo\n.foo:\n    rts\n")
        w005_lines = [l for l in stderr.splitlines() if "W005" in l]
        self.assertTrue(len(w005_lines) > 0)
        self.assertIn("suggestion:", w005_lines[0])
        self.assertNotIn("warning:", w005_lines[0])

    def test_summary_three_tier(self):
        """Summary shows separate suggestion count."""
        _, stderr = self._run("; header\n; ---\nMyRoutine:\n    bne.w .foo\n.foo:\n    rts\n")
        summary_line = [l for l in stderr.splitlines() if l.startswith("s4lint:")]
        self.assertTrue(len(summary_line) > 0)
        self.assertIn("suggestion", summary_line[0])

    def test_no_suggestions_flag(self):
        """--no-suggestions hides suggestions but shows warnings."""
        _, stderr = self._run(
            "; header\n; ---\nMyRoutine:\n    clr.w (a0)\n    bne.w .foo\n.foo:\n    rts\n",
            extra_args=["--no-suggestions"],
        )
        self.assertNotIn("W005", stderr)
        self.assertIn("W001", stderr)

    def test_no_warnings_suppresses_suggestions_too(self):
        """--no-warnings hides both warnings and suggestions."""
        _, stderr = self._run(
            "; header\n; ---\nMyRoutine:\n    clr.w (a0)\n    bne.w .foo\n.foo:\n    rts\n",
            extra_args=["--no-warnings"],
        )
        self.assertNotIn("W005", stderr)
        self.assertNotIn("W001", stderr)
        self.assertIn("no issues found", stderr)

    def test_suggestions_dont_affect_exit_code(self):
        """Suggestions alone should not cause exit code 1."""
        code, _ = self._run("; header\n; ---\nMyRoutine:\n    bne.w .foo\n.foo:\n    rts\n")
        self.assertEqual(code, 0)

    def test_warnings_as_errors_ignores_suggestions(self):
        """--warnings-as-errors promotes warnings but not suggestions."""
        code, stderr = self._run(
            "; header\n; ---\nMyRoutine:\n    bne.w .foo\n.foo:\n    rts\n",
            extra_args=["--warnings-as-errors"],
        )
        w005_lines = [l for l in stderr.splitlines() if "W005" in l]
        self.assertTrue(len(w005_lines) > 0)
        self.assertIn("suggestion:", w005_lines[0])
        self.assertEqual(code, 0)

    def test_summary_omits_zero_counts(self):
        """Summary omits tiers with zero count."""
        _, stderr = self._run(
            "; header\n; ---\nClean:\n    rts\n",
            extra_args=["--skip=W006,W018"],
        )
        self.assertIn("no issues found", stderr)


# ---------------------------------------------------------------------------
# W020: tail call — bsr/jsr immediately before rts
# ---------------------------------------------------------------------------

class TestW020_TailCall(unittest.TestCase):

    def _diags(self, lines_str):
        """Lint a snippet and return diagnostics."""
        content = "; header\n; ---\nTestRoutine:\n" + lines_str
        with tempfile.NamedTemporaryFile(mode="w", suffix=".asm", delete=False) as f:
            f.write(content)
            f.flush()
            fname = f.name
        try:
            ctx = lint_file(fname, {
                "no_warnings": False,
                "warnings_as_errors": False,
                "no_suggestions": False,
            }, os.path.dirname(fname))
            return ctx.diagnostics
        finally:
            os.unlink(fname)

    def test_bsr_then_rts_warns(self):
        """bsr followed by rts should trigger W020."""
        diags = self._diags("    bsr.w SomeRoutine\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 1)
        self.assertIn("bra.w", w020[0].message)
        self.assertEqual(w020[0].severity, "warning")

    def test_jsr_then_rts_warns(self):
        """jsr followed by rts should trigger W020."""
        diags = self._diags("    jsr SomeRoutine\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 1)
        self.assertIn("jmp", w020[0].message)

    def test_bsr_with_label_between_no_warn(self):
        """bsr followed by a label then rts should NOT trigger W020."""
        diags = self._diags("    bsr.w SomeRoutine\n.local_entry:\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_bsr_with_global_label_between_no_warn(self):
        """bsr followed by a global label then rts should NOT trigger W020."""
        diags = self._diags("    bsr.w SomeRoutine\nOtherEntry:\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_bsr_then_other_instr_no_warn(self):
        """bsr followed by a non-rts instruction should NOT trigger W020."""
        diags = self._diags("    bsr.w SomeRoutine\n    nop\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_standalone_rts_no_warn(self):
        """rts without a preceding bsr/jsr should NOT trigger W020."""
        diags = self._diags("    move.w d0, d1\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_bsr_s_then_rts_warns(self):
        """bsr.s followed by rts should also trigger W020 (use bra.s)."""
        diags = self._diags("    bsr.s SomeRoutine\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 1)
        self.assertIn("bra.s", w020[0].message)

    def test_w020_suppressed(self):
        """W020 should be suppressible via inline comment."""
        diags = self._diags("    bsr.w SomeRoutine\n    rts ; lint: disable=W020\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_bsr_then_rte_no_warn(self):
        """bsr before rte is not a tail call — rte restores SR+PC, not just PC."""
        diags = self._diags("    bsr.w Helper\n    rte\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 0)

    def test_bsr_unsized_suggests_bra_w(self):
        """Bare bsr (no size) should suggest bra.w as the default."""
        diags = self._diags("    bsr SomeRoutine\n    rts\n")
        w020 = [d for d in diags if d.code == "W020"]
        self.assertEqual(len(w020), 1)
        self.assertIn("bra.w", w020[0].message)


if __name__ == "__main__":
    unittest.main()
