; ===============================================================
; MD Debugger exported symbols (MDDBG__*) — the AS-side equ table.
;
; ALWAYS assembled (both gate states), so debugger.asm's assert/RaiseError
; macro expansions resolve MDDBG__ErrorHandler / _PagesController even when the
; error_handler region is .emp-owned (SIGIL_EMP_ERROR_HANDLER): every entry
; derives off `ErrorHandler`, which is the blob label in the pure-AS build and a
; NUMERIC per-shape equ in the mixed build (engine.inc gate-ON arm) — so the
; derivation folds at assemble time (no link-time-equ-off-external-base needed).
; Emits ZERO bytes.
; ---------------------------------------------------------------
; MD Debugger's exported symbols
; ---------------------------------------------------------------

MDDBG__ErrorHandler: equ ErrorHandler+$0
MDDBG__Error_IdleLoop: equ ErrorHandler+$128
MDDBG__Error_InitConsole: equ ErrorHandler+$142
MDDBG__Error_MaskStackBoundaries: equ ErrorHandler+$14E
MDDBG__Error_DrawOffsetLocation: equ ErrorHandler+$1B8
MDDBG__Error_DrawOffsetLocation2: equ ErrorHandler+$1BC
MDDBG__Error_DrawOffsetLocation__inj: equ ErrorHandler+$1C2
MDDBG__ErrorHandler_SetupVDP: equ ErrorHandler+$250
MDDBG__ErrorHandler_VDPConfig: equ ErrorHandler+$286
MDDBG__ErrorHandler_VDPConfig_Nametables: equ ErrorHandler+$29C
MDDBG__ErrorHandler_ConsoleConfig_Initial: equ ErrorHandler+$2D8
MDDBG__ErrorHandler_ConsoleConfig_Shared: equ ErrorHandler+$2DC
MDDBG__Str_OffsetLocation_24bit: equ ErrorHandler+$30C
MDDBG__Str_OffsetLocation_32bit: equ ErrorHandler+$315
MDDBG__Art1bpp_Font: equ ErrorHandler+$350
MDDBG__GetSymbolByOffset: equ ErrorHandler+$64A
MDDBG__FormatString: equ ErrorHandler+$960
MDDBG__Console_Init: equ ErrorHandler+$A3A
MDDBG__Console_Reset: equ ErrorHandler+$A78
MDDBG__Console_InitShared: equ ErrorHandler+$A7A
MDDBG__Console_SetPosAsXY_Stack: equ ErrorHandler+$AC4
MDDBG__Console_SetPosAsXY: equ ErrorHandler+$ACA
MDDBG__Console_GetPosAsXY: equ ErrorHandler+$AFE
MDDBG__Console_StartNewLine: equ ErrorHandler+$B24
MDDBG__Console_SetBasePattern: equ ErrorHandler+$B52
MDDBG__Console_SetWidth: equ ErrorHandler+$B6E
MDDBG__Console_WriteLine_WithPattern: equ ErrorHandler+$B8C
MDDBG__Console_WriteLine: equ ErrorHandler+$B8E
MDDBG__Console_Write: equ ErrorHandler+$B92
MDDBG__Console_WriteLine_Formatted: equ ErrorHandler+$C58
MDDBG__Console_Write_Formatted: equ ErrorHandler+$C5C
MDDBG__Decomp1bpp: equ ErrorHandler+$C8C
MDDBG__KDebug_WriteLine_Formatted: equ ErrorHandler+$CA8
MDDBG__KDebug_Write_Formatted: equ ErrorHandler+$CAC
MDDBG__KDebug_FlushLine: equ ErrorHandler+$D00
MDDBG__KDebug_WriteLine: equ ErrorHandler+$D0A
MDDBG__KDebug_Write: equ ErrorHandler+$D0E
MDDBG__ErrorHandler_ConsoleOnly: equ ErrorHandler+$D3C
MDDBG__ErrorHandler_ClearConsole: equ ErrorHandler+$D62
MDDBG__ErrorHandler_PauseConsole: equ ErrorHandler+$D8C
MDDBG__ErrorHandler_PagesController: equ ErrorHandler+$DC6
MDDBG__VSync: equ ErrorHandler+$E26
MDDBG__ErrorHandler_ExtraDebuggerList: equ ErrorHandler+$E60
MDDBG__Debugger_AddressRegisters: equ ErrorHandler+$E6C
MDDBG__Debugger_Backtrace: equ ErrorHandler+$EB8
