#!/usr/bin/env osascript
-- excel_model.applescript - controlled Microsoft Excel automation for the investing skills.
--
-- Every command that touches a workbook hardens Excel first (macros disabled, link
-- updates off, alerts suppressed, manual calculation), restores the previous
-- application settings on success AND failure, and refuses to run when unrelated
-- workbooks are open, because Excel's calculate command affects all open workbooks.
--
-- Usage:
--   osascript excel_model.applescript status
--   osascript excel_model.applescript recalc workbook=/abs/copy.xlsx [readback=/abs/cells.tsv] [out=/abs/report.tsv] [calc=full|dirty|rebuild] [save=no] [close=no] [allowOtherWorkbooks=yes] [timeout=600]
--   osascript excel_model.applescript edit   workbook=/abs/copy.xlsx changes=/abs/changes.tsv [readback=...] [out=...] [save=no] [close=no]
--   osascript excel_model.applescript close workbook=/abs/copy.xlsx [workbook=/abs/other.xlsx]
--   osascript excel_model.applescript settings-get
--   osascript excel_model.applescript help
--
-- Argument style is key=value with no leading dashes: osascript consumes dashed
-- options of its own before handing arguments to the script.
--
-- changes.tsv  one change per line:  sheet <tab> cell <tab> kind <tab> content
--              kind is one of: formula | number | text | clear
-- readback.tsv one cell per line:    sheet <tab> cell
--
-- Report (also printed to stdout): tab-separated records, one per line,
--   STATUS / MESSAGE / APP / OTHER_WORKBOOK / WORKBOOK / CALC / CELL / CELL_ERROR /
--   CHANGE / CHANGE_ERROR / SAVED / CLOSED / SKIPPED / RESTORED / SETTING.
--   STATUS is OK, or BLOCKED/ERROR on failure.
--
-- `close` closes only workbooks whose full path appears in an explicit workbook=
-- argument; it never closes anything else and never saves.
--
-- timeout=  AppleEvent timeout in seconds for the Excel calls (default 600). A
-- modal dialog in Excel queues AppleEvents, and the AppleScript default (120s)
-- turns that into a misleading -1712 ""timed out"" error, so the timeout is
-- explicit and a timeout is reported as such.
--
-- This script never writes to a path it was not told to open. It does not guess
-- cell locations and does not repair anything on its own.

property okStatus : "OK"
-- Inside a tell-application block a bare `tab` resolves to Excel's own property,
-- so the tab character is carried in a property of this script instead.
property TABCHAR : tab
property blockedStatus : "BLOCKED"
property errorStatus : "ERROR"

on run argv
	if (count of argv) = 0 then return usage()
	set theCommand to item 1 of argv
	if theCommand is "status" then
		return cmdStatus()
	else if theCommand is "settings-get" then
		return cmdSettingsGet()
	else if theCommand is "help" then
		return usage()
	else if theCommand is "recalc" then
		return cmdProcess(argv, false)
	else if theCommand is "edit" then
		return cmdProcess(argv, true)
	else if theCommand is "close" then
		return cmdClose(argv, excelWasRunningAtStart())
	else
		return my reportLine("STATUS", errorStatus) & my LF() & my reportLine("MESSAGE", "unknown command: " & theCommand) & my LF() & usage()
	end if
end run

-- ----------------------------------------------------------------- structure

on LF()
	return (ASCII character 10)
end LF

-- NB: names that also exist in Excel's scripting dictionary (`key`, `text`, `data`,
-- `number`, `kind`, `content`, `summary`, `ask`, `calculation`) resolve to Excel's
-- property inside a `tell application "Microsoft Excel"` block instead of to this
-- script's variable, so they must not be used for locals or parameters.
-- tests/test_applescript_scoping.py checks this mechanically.
on reportLine(labelName, lineValue)
	return labelName & TABCHAR & lineValue
end reportLine

on usage()
	return "commands: status | recalc | edit | close | settings-get | help" & my LF()
end usage

on getOption(argsList, theKey)
	set prefix to theKey & "="
	repeat with i from 1 to (count of argsList)
		set theArg to item i of argsList
		if theArg starts with prefix then return text ((length of prefix) + 1) thru -1 of theArg
	end repeat
	return missing value
end getOption

on writeTextFile(filePath, theText)
	try
		set f to open for access (POSIX file filePath) with write permission
		set eof f to 0
		write theText to f as «class utf8»
		close access f
		return true
	on error
		try
			close access (POSIX file filePath)
		end try
		return false
	end try
end writeTextFile

-- `do shell script` rewrites line endings unless told not to, so it is told not to
-- and `paragraphs` (which splits on either CR or LF) does the splitting.
on readLines(filePath)
	set theText to do shell script "cat " & quoted form of filePath without altering line endings
	if theText is "" then return {}
	set cleanLines to {}
	repeat with aLine in (paragraphs of theText)
		set s to my trim(aLine as text)
		if s is not "" then set end of cleanLines to s
	end repeat
	return cleanLines
end readLines

on splitByTab(theLine)
	set prevDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to TABCHAR
	set theParts to text items of theLine
	set AppleScript's text item delimiters to prevDelims
	return theParts
end splitByTab

on trim(theText)
	set s to theText as text
	repeat while s starts with " "
		set s to text 2 thru -1 of s
	end repeat
	repeat while s ends with " "
		set s to text 1 thru -2 of s
	end repeat
	return s
end trim

-- -------------------------------------------------------------- app settings

-- Snapshot of the application-level settings this script changes.
on appSettings()
	tell application "Microsoft Excel"
		set calcSetting to "unknown"
		try
			set calcSetting to (calculation as text)
		end try
		return {calc:calcSetting, alerts:(display alerts as text), askLinks:(ask to update links as text), autoSec:(automation security as text)}
	end tell
end appSettings

on excelWasRunningAtStart()
	return (application "Microsoft Excel" is running)
end excelWasRunningAtStart

-- Close only workbooks named explicitly on the command line (never saving).
on cmdClose(argsList, excelWasRunning)
	set wanted to {}
	repeat with i from 1 to (count of argsList)
		set theArg to item i of argsList
		if theArg starts with "workbook=" then set end of wanted to text 10 thru -1 of theArg
	end repeat
	if (count of wanted) = 0 then return my fatal("close requires at least one workbook= argument")

	set out to ""
	set closedAny to false
	set preState to my appSettings()
	try
		tell application "Microsoft Excel"
			set display alerts to false
			repeat with i from 1 to (count of workbooks)
				set wb to workbook i
				set wbFull to full name of wb
				set wbName to name of wb
				if wanted contains wbFull then
					close wb saving false
					set out to out & "CLOSED" & TABCHAR & wbName & TABCHAR & wbFull & my LF()
					set closedAny to true
				else
					set out to out & "SKIPPED" & TABCHAR & wbName & TABCHAR & wbFull & my LF()
				end if
			end repeat
		end tell
		if not excelWasRunning then
			tell application "Microsoft Excel"
				set stillOpen to (count of workbooks)
			end tell
			if stillOpen = 0 then
				tell application "Microsoft Excel" to quit
				set out to out & "APP" & TABCHAR & "excel_quit" & TABCHAR & "true" & my LF()
			end if
		end if
		-- Restore whatever Excel's settings were, never a hardcoded value.
		set restored to my restoreSettings(preState)
		set out to out & "RESTORED" & TABCHAR & restored & my LF()
		if not closedAny then set out to out & "CLOSED" & TABCHAR & "none-matching" & TABCHAR & "no open workbook matched" & my LF()
		return my reportLine("STATUS", okStatus) & my LF() & out
	on error errMsg number errNum
		set restored to my restoreSettings(preState)
		return my reportLine("STATUS", errorStatus) & my LF() & my reportLine("MESSAGE", "(" & errNum & ") " & errMsg) & my LF() & "RESTORED" & TABCHAR & restored & my LF()
	end try
end cmdClose

on cmdSettingsGet()
	try
		set s to my appSettings()
		set out to my reportLine("STATUS", okStatus) & my LF()
		set out to out & "SETTING" & TABCHAR & "calculation" & TABCHAR & (calc of s) & my LF()
		set out to out & "SETTING" & TABCHAR & "display_alerts" & TABCHAR & (alerts of s) & my LF()
		set out to out & "SETTING" & TABCHAR & "ask_to_update_links" & TABCHAR & (askLinks of s) & my LF()
		set out to out & "SETTING" & TABCHAR & "automation_security" & TABCHAR & (autoSec of s) & my LF()
		return out
	on error errMsg number errNum
		return my reportLine("STATUS", errorStatus) & my LF() & my reportLine("MESSAGE", "(" & errNum & ") " & errMsg) & my LF()
	end try
end cmdSettingsGet

-- Enum constants only resolve inside a tell block, so map them there.
on calcModeFromText(txt)
	tell application "Microsoft Excel"
		if txt is "calculation automatic" then return calculation automatic
		if txt is "calculation manual" then return calculation manual
		if txt is "calculation semiautomatic" then return calculation semiautomatic
	end tell
	return missing value
end calcModeFromText

-- Restore the settings captured before hardening. Never fails loudly, but reads the
-- settings back afterwards so the report shows what Excel actually holds, not what
-- this script intended to write.
on restoreSettings(s)
	tell application "Microsoft Excel"
		try
			set m to my calcModeFromText(calc of s)
			if m is not missing value then set calculation to m
		end try
		try
			set display alerts to (alerts of s is "true")
		end try
		try
			set ask to update links to (askLinks of s is "true")
		end try
		try
			if (autoSec of s) is "msoAutomationSecurityLow" then
				set automation security to msoAutomationSecurityLow
			else if (autoSec of s) is "msoAutomationSecurityByUI" then
				set automation security to msoAutomationSecurityByUI
			else if (autoSec of s) is "msoAutomationSecurityForceDisable" then
				set automation security to msoAutomationSecurityForceDisable
			end if
		end try
	end tell
	set post1 to my appSettings()
	set mismatch to ""
	if (alerts of post1) is not (alerts of s) then set mismatch to mismatch & "display_alerts;"
	if (askLinks of post1) is not (askLinks of s) then set mismatch to mismatch & "ask_to_update_links;"
	if (autoSec of post1) is not (autoSec of s) then set mismatch to mismatch & "automation_security;"
	-- Excel reports `missing value` for the calculation mode when no workbook is
	-- open (before the first open, or after closing the last one). Then there is
	-- nothing to restore and nothing to compare, which is stated rather than
	-- reported as a failed restore.
	set calcComparable to ((calc of s) is not "missing value") and ((calc of post1) is not "missing value")
	if calcComparable and (calc of post1) is not (calc of s) then set mismatch to mismatch & "calculation;"
	set restoreSummary to "calc=" & (calc of post1) & ";alerts=" & (alerts of post1) & ";askLinks=" & (askLinks of post1) & ";autoSec=" & (autoSec of post1)
	if not calcComparable then set restoreSummary to restoreSummary & ";calculation_not_comparable_no_open_workbook"
	if mismatch is "" then
		return restoreSummary & ";match=true"
	else
		return restoreSummary & ";match=false;mismatch=" & mismatch
	end if
end restoreSettings

-- ---------------------------------------------------------------------- status

on cmdStatus()
	set out to ""
	try
		set excelRunning to application "Microsoft Excel" is running
		set out to out & "APP" & TABCHAR & "excel_running" & TABCHAR & (excelRunning as text) & my LF()
		if excelRunning then
			tell application "Microsoft Excel"
				set out to out & "APP" & TABCHAR & "excel_version" & TABCHAR & (version as text) & my LF()
				set out to out & "APP" & TABCHAR & "workbook_count" & TABCHAR & (count of workbooks as text) & my LF()
				repeat with i from 1 to (count of workbooks)
					set wb to workbook i
					set out to out & "OTHER_WORKBOOK" & TABCHAR & (name of wb) & TABCHAR & (full name of wb) & my LF()
				end repeat
				try
					set out to out & "APP" & TABCHAR & "calculation" & TABCHAR & (calculation as text) & my LF()
				end try
				set out to out & "APP" & TABCHAR & "display_alerts" & TABCHAR & (display alerts as text) & my LF()
				set out to out & "APP" & TABCHAR & "ask_to_update_links" & TABCHAR & (ask to update links as text) & my LF()
				try
					set out to out & "APP" & TABCHAR & "automation_security" & TABCHAR & (automation security as text) & my LF()
				end try
			end tell
		end if
		return my reportLine("STATUS", okStatus) & my LF() & out
	on error errMsg number errNum
		return my reportLine("STATUS", errorStatus) & my LF() & my reportLine("MESSAGE", "(" & errNum & ") " & errMsg) & my LF()
	end try
end cmdStatus

-- ------------------------------------------------------------- recalc / edit

on cmdProcess(argsList, doEdits)
	set wbPath to my getOption(argsList, "workbook")
	if wbPath is missing value then return my fatal("workbook= is required")
	set changesPath to my getOption(argsList, "changes")
	if doEdits and changesPath is missing value then return my fatal("changes= is required for edit")
	set readbackPath to my getOption(argsList, "readback")
	set outPath to my getOption(argsList, "out")
	set calcRequest to my getOption(argsList, "calc")
	if calcRequest is missing value then set calcRequest to "full"
	set saveFlag to (my getOption(argsList, "save") is not "no")
	set closeFlag to (my getOption(argsList, "close") is not "no")
	set allowOthers to (my getOption(argsList, "allowOtherWorkbooks") is "yes")
	set timeoutOption to my getOption(argsList, "timeout")
	set opTimeout to 600
	if timeoutOption is not missing value then
		try
			set opTimeout to (timeoutOption as integer)
		end try
	end if

	if doShellCommand("test -f " & quoted form of wbPath & " && echo yes") is not "yes" then
		return my fatal("workbook not found: " & wbPath)
	end if

	set excelWasRunning to my excelWasRunningAtStart()
	set out to ""

	set fileCalcMode to my workbookCalcModeValue(wbPath)

	-- Refuse to work when unrelated workbooks are open: Excel's calculate command
	-- recalculates every open workbook.
	if excelWasRunning and not allowOthers then
		tell application "Microsoft Excel"
			if (count of workbooks) > 0 then
				set others to ""
				repeat with i from 1 to (count of workbooks)
					set others to others & (name of workbook i) & " | "
				end repeat
				set out to out & my reportLine("STATUS", blockedStatus) & my LF()
				set out to out & my reportLine("MESSAGE", "unrelated workbooks open in Excel: " & others & "close them or grant exclusive use, then retry") & my LF()
				return my finish(out, outPath)
			end if
		end tell
	end if

	set out to out & "APP" & TABCHAR & "appleevent_timeout_seconds" & TABCHAR & (opTimeout as text) & my LF()

	with timeout of opTimeout seconds
	set preState to my appSettings()
	set openedWbName to missing value
	set out to out & "CALC" & TABCHAR & "file_declared_mode" & TABCHAR & fileCalcMode & my LF()
	set didSave to false

	try
		tell application "Microsoft Excel"
			-- Harden before opening anything unfamiliar.
			set display alerts to false
			set ask to update links to false
			set automation security to msoAutomationSecurityForceDisable
			set calculation to calculation manual

			set wb to open workbook workbook file name wbPath update links do not update links read only false ignore read only recommended true add to mru false
			-- If the same path is already open in Excel, `open workbook` returns without
			-- binding the result object; fail loudly instead of silently doing nothing.
			try
				set openedWbName to name of wb
			on error
				error "open workbook returned no workbook object for " & wbPath & " - is that file already open in Excel?"
			end try
			set out to out & "WORKBOOK" & TABCHAR & "opened" & TABCHAR & openedWbName & my LF()
			set out to out & "WORKBOOK" & TABCHAR & "full_name" & TABCHAR & (full name of wb) & my LF()
			set out to out & "WORKBOOK" & TABCHAR & "sheets" & TABCHAR & (count of sheets of wb as text) & my LF()

			set calculation to calculation manual
			set out to out & "CALC" & TABCHAR & "mode_before" & TABCHAR & (calculation as text) & my LF()

			-- Apply approved changes before recalculation so downstream effects are visible.
			if doEdits then
				set changeLines to my readLines(changesPath)
				set appliedCount to 0
				set failedCount to 0
				repeat with aLine in changeLines
					set parts to my splitByTab(aLine as text)
					if (count of parts) >= 4 then
						set sheetName to my trim(item 1 of parts)
						set cellAddr to my trim(item 2 of parts)
						set changeKind to my trim(item 3 of parts)
						set changeContent to item 4 of parts
						if (count of parts) > 4 then
							repeat with p from 5 to (count of parts)
								set changeContent to changeContent & TABCHAR & (item p of parts)
							end repeat
						end if
						try
							set changeSummary to my applyChange(wb, sheetName, cellAddr, changeKind, changeContent)
							set out to out & "CHANGE" & TABCHAR & sheetName & TABCHAR & cellAddr & TABCHAR & changeKind & TABCHAR & changeSummary & my LF()
							set appliedCount to appliedCount + 1
						on error errMsg number errNum
							set out to out & "CHANGE_ERROR" & TABCHAR & sheetName & TABCHAR & cellAddr & TABCHAR & changeKind & TABCHAR & "(" & errNum & ") " & errMsg & my LF()
							set failedCount to failedCount + 1
						end try
					end if
				end repeat
				set out to out & "CHANGE" & TABCHAR & "*" & TABCHAR & "*" & TABCHAR & "count" & TABCHAR & (appliedCount as text) & my LF()
				if failedCount > 0 then error "one or more changes failed to apply"
			end if

			-- Excel's AppleScript has no per-workbook calculate: `calculate <workbook>`
			-- raises -50, while `calculate full` recalculates every open workbook.
			-- Exclusivity was enforced above, so only our copy is affected.
			if calcRequest is "dirty" then
				calculate
				set out to out & "CALC" & TABCHAR & "calculated" & TABCHAR & "calculate" & my LF()
			else if calcRequest is "rebuild" then
				calculate full rebuild
				set out to out & "CALC" & TABCHAR & "calculated" & TABCHAR & "calculate full rebuild" & my LF()
			else
				calculate full
				set out to out & "CALC" & TABCHAR & "calculated" & TABCHAR & "calculate full" & my LF()
			end if

			if readbackPath is not missing value then
				set rbLines to my readLines(readbackPath)
				repeat with aLine in rbLines
					set parts to my splitByTab(aLine as text)
					if (count of parts) >= 2 then
						set sheetName to my trim(item 1 of parts)
						set cellAddr to my trim(item 2 of parts)
						set out to out & my describeCell(wb, sheetName, cellAddr) & my LF()
					else
						set out to out & "CELL_ERROR" & TABCHAR & "malformed readback line" & TABCHAR & (aLine as text) & my LF()
					end if
				end repeat
			end if

			if saveFlag then
				-- Keep the workbook's own calculation mode rather than ours.
				if fileCalcMode is "manual" then
					set calculation to calculation manual
				else
					set calculation to calculation automatic
				end if
				save wb
				set didSave to true
				set out to out & "CALC" & TABCHAR & "saved_with_mode" & TABCHAR & (calculation as text) & my LF()
				if fileCalcMode is "autoNoTable" then
					set out to out & "WARNING" & TABCHAR & "workbook declared autoNoTable; AppleScript cannot set that exception, so it was saved as automatic" & my LF()
				end if
				set out to out & "SAVED" & TABCHAR & (full name of wb) & my LF()
			end if

			if closeFlag then
				close wb saving false
				set out to out & "CLOSED" & TABCHAR & openedWbName & my LF()
			end if
		end tell
	on error errMsg number errNum
		-- Best effort: leave Excel as we found it, without killing it.
		try
			if openedWbName is not missing value then
				tell application "Microsoft Excel" to close workbook openedWbName saving false
			end if
		end try
		set restored to my restoreSettings(preState)
		set out to out & my reportLine("STATUS", errorStatus) & my LF()
		set out to out & my reportLine("MESSAGE", "(" & errNum & ") " & errMsg) & my LF()
		if errNum is -1712 then
			set out to out & my reportLine("MESSAGE", "Excel did not answer within " & (opTimeout as text) & "s: a modal dialog is probably open in Excel (dismiss it) or the file needs interactive approval") & my LF()
		end if
		set out to out & "RESTORED" & TABCHAR & restored & my LF()
		return my finish(out, outPath)
	end try

	set restored to my restoreSettings(preState)
	set out to out & "RESTORED" & TABCHAR & restored & my LF()
	set out to out & "APP" & TABCHAR & "saved" & TABCHAR & (didSave as text) & my LF()

	-- Quit only when this script started Excel and nothing is left open in it.
	if not excelWasRunning and closeFlag then
		try
			tell application "Microsoft Excel"
				if (count of workbooks) = 0 then quit
			end tell
			set out to out & "APP" & TABCHAR & "excel_quit" & TABCHAR & "true" & my LF()
		on error
			set out to out & "APP" & TABCHAR & "excel_quit" & TABCHAR & "false" & my LF()
		end try
	end if

	return my finish(my reportLine("STATUS", okStatus) & my LF() & out, outPath)
	end timeout
end cmdProcess

on finish(out, outPath)
	if outPath is not missing value then
		if not writeTextFile(outPath, out) then
			return out & "WARNING" & TABCHAR & "could not write report file " & outPath & my LF()
		end if
	end if
	return out
end finish

on fatal(msg)
	return my reportLine("STATUS", errorStatus) & my LF() & my reportLine("MESSAGE", msg) & my LF()
end fatal

on doShellCommand(cmd)
	try
		return do shell script cmd
	on error
		return ""
	end try
end doShellCommand

-- Excel writes the *application-level* calculation mode into the workbook when it
-- saves, so a manual run would silently flip an automatic workbook to manual. Read
-- the mode the file itself declares and restore it before saving.
on workbookCalcModeValue(filePath)
	set raw to my doShellCommand("unzip -p " & quoted form of filePath & " xl/workbook.xml 2>/dev/null | tr '>' '\\n' | grep -o 'calcMode=\"[a-zA-Z]*\"' | head -1")
	if raw contains "manual" then return "manual"
	if raw contains "autoNoTable" then return "autoNoTable"
	return "auto"
end workbookCalcModeValue

-- Apply one change and return a human summary of the before/after state.
on applyChange(wb, sheetName, cellAddr, changeKind, changeContent)
	tell application "Microsoft Excel"
		set theSheet to worksheet sheetName of wb
		set theRange to range cellAddr of theSheet
		set beforeText to "empty"
		try
			set beforeText to (formula of theRange as text)
		end try
		if changeKind is "formula" then
			set formula of theRange to changeContent
		else if changeKind is "number" then
			set value of theRange to (changeContent as real)
		else if changeKind is "text" then
			set value of theRange to changeContent
		else if changeKind is "clear" then
			clear contents theRange
		else
			error "unknown change kind: " & changeKind
		end if
		set afterText to (formula of theRange as text)
		return "before[" & beforeText & "] after[" & afterText & "]"
	end tell
end applyChange

-- Read one cell as formula / value / displayed text, flagging error values.
on describeCell(wb, sheetName, cellAddr)
	tell application "Microsoft Excel"
		set fText to ""
		try
			set theRange to range cellAddr of worksheet sheetName of wb
		on error errMsg number errNum
			return "CELL_ERROR" & TABCHAR & sheetName & TABCHAR & cellAddr & TABCHAR & "(" & errNum & ") " & errMsg
		end try
		try
			set fText to (formula of theRange as text)
		end try
		set vText to ""
		set isError to "false"
		try
			set v to value of theRange
			if v is missing value then
				set isError to "true"
				set vText to "#ERROR"
			else
				set vText to (v as text)
			end if
		on error
			set isError to "true"
			set vText to "#ERROR"
		end try
		set tText to ""
		try
			set tText to (text of theRange as text)
		end try
		return "CELL" & TABCHAR & sheetName & TABCHAR & cellAddr & TABCHAR & fText & TABCHAR & vText & TABCHAR & tText & TABCHAR & isError
	end tell
end describeCell
