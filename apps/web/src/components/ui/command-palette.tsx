"use client";

import { type KeyboardEvent, useMemo, useState } from "react";
import { Icon, type IconName } from "./icons";

export type Command = { id: string; label: string; group: string; icon: IconName; hint?: string; disabled?: boolean; run: () => void };

/** Mounted only while open, so its query and selection start fresh every time. */
export function CommandPalette({ commands, onClose }: { commands: Command[]; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return commands.filter((command) => !command.disabled && (!needle || `${command.group} ${command.label}`.toLowerCase().includes(needle)));
  }, [commands, query]);
  const selected = Math.min(index, Math.max(results.length - 1, 0));

  function execute(command: Command | undefined) {
    if (!command) return;
    onClose();
    command.run();
  }

  function navigate(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); onClose(); }
    if (event.key === "ArrowDown") { event.preventDefault(); setIndex((selected + 1) % Math.max(results.length, 1)); }
    if (event.key === "ArrowUp") { event.preventDefault(); setIndex((selected - 1 + results.length) % Math.max(results.length, 1)); }
    if (event.key === "Enter") { event.preventDefault(); execute(results[selected]); }
  }

  return (
    <div className="palette-backdrop" onPointerDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="palette glass-strong" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={navigate}>
        <label className="palette-search">
          <Icon name="search" size={18} />
          <input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setIndex(0); }} placeholder="Search views and actions…" aria-label="Search commands" role="combobox" aria-expanded="true" aria-controls="palette-results" aria-activedescendant={results[selected] ? `cmd-${results[selected].id}` : undefined} />
          <kbd className="kbd">esc</kbd>
        </label>
        <ul id="palette-results" role="listbox" className="palette-results">
          {results.length === 0 && <li className="palette-empty">No matching commands</li>}
          {results.map((command, position) => {
            const header = position === 0 || results[position - 1].group !== command.group ? command.group : null;
            return (
              <li key={command.id} role="presentation">
                {header && <span className="palette-group">{header}</span>}
                <button id={`cmd-${command.id}`} type="button" role="option" aria-selected={position === selected} className={position === selected ? "active" : ""} onPointerMove={() => setIndex(position)} onClick={() => execute(command)}>
                  <Icon name={command.icon} size={16} />
                  <span>{command.label}</span>
                  {command.hint && <kbd className="kbd">{command.hint}</kbd>}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
