/**
 * JSON Editor Component
 * 
 * 基於 CodeMirror 6 的 JSON 編輯器，支援：
 * - JSON 語法高亮
 * - 自動括號配對
 * - 錯誤指示
 * - Undo/Redo
 */

import { useEffect, useRef, useCallback } from 'react';
import { EditorState } from '@codemirror/state';
import { EditorView, keymap, placeholder as cmPlaceholder } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { json } from '@codemirror/lang-json';
import { linter, lintGutter } from '@codemirror/lint';
import type { Diagnostic } from '@codemirror/lint';
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete';
import { syntaxHighlighting, HighlightStyle } from '@codemirror/language';
import { tags } from '@lezer/highlight';

interface JsonEditorProps {
    value: string;
    onChange: (value: string) => void;
    onValidChange?: (isValid: boolean, error?: string) => void;
    placeholder?: string;
    className?: string;
    style?: React.CSSProperties;
    height?: string;
}

// JSON 驗證 linter
const jsonLinter = linter((view) => {
    const diagnostics: Diagnostic[] = [];
    const text = view.state.doc.toString();

    if (text.trim()) {
        try {
            JSON.parse(text);
        } catch (e: any) {
            // 嘗試從錯誤訊息中提取位置
            const match = e.message.match(/at position (\d+)/);
            const pos = match ? parseInt(match[1]) : 0;

            diagnostics.push({
                from: Math.min(pos, text.length),
                to: Math.min(pos + 1, text.length),
                severity: 'error',
                message: e.message,
            });
        }
    }

    return diagnostics;
});

export const JsonEditor = ({
    value,
    onChange,
    onValidChange,
    placeholder = '',
    className = '',
    style = {},
    height = '100px',
}: JsonEditorProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewRef = useRef<EditorView | null>(null);
    const isExternalUpdate = useRef(false);

    // 初始化編輯器
    useEffect(() => {
        if (!containerRef.current) return;

        const updateListener = EditorView.updateListener.of((update) => {
            if (update.docChanged && !isExternalUpdate.current) {
                const text = update.state.doc.toString();
                onChange(text);

                // 驗證 JSON
                if (onValidChange) {
                    try {
                        if (text.trim()) {
                            JSON.parse(text);
                        }
                        onValidChange(true);
                    } catch (e: any) {
                        onValidChange(false, e.message);
                    }
                }
            }
        });

        const theme = EditorView.theme({
            '&': {
                height: height,
                fontSize: '12px',
                fontFamily: '"SF Mono", Monaco, "Cascadia Code", monospace',
            },
            '.cm-content': {
                padding: '10px 12px',
                caretColor: '#3b82f6',
            },
            '.cm-focused': {
                outline: 'none',
            },
            '.cm-line': {
                lineHeight: '1.5',
            },
            '.cm-cursor': {
                borderLeftColor: '#3b82f6',
                borderLeftWidth: '2px',
            },
            '.cm-placeholder': {
                color: '#9ca3af',
            },
            '.cm-gutters': {
                backgroundColor: '#f9fafb',
                borderRight: '1px solid #e5e7eb',
            },
            '.cm-lint-marker-error': {
                content: '""',
            },
            // JSON 語法顏色
            '.cm-string': {
                color: '#059669',  // 綠色：字串
            },
            '.cm-number': {
                color: '#d97706',  // 橙色：數字
            },
            '.cm-bool': {
                color: '#7c3aed',  // 紫色：布林
            },
            '.ͼb': {  // JSON string - CodeMirror uses ͼ prefix for syntax
                color: '#2563eb !important',  // 藍色：字串值
            },
            '.ͼc': {  // JSON number
                color: '#d97706 !important',  // 橙色：數字
            },
            '.ͼd': {  // JSON bool / null / keyword
                color: '#7c3aed !important',  // 紫色：布林
            },
            '.ͼe': {  // JSON property name (key)
                color: '#059669 !important',  // 綠色：key
            },
        });
        // 自訂 JSON 語法高亮
        const jsonHighlightStyle = HighlightStyle.define([
            { tag: tags.propertyName, color: '#059669' },  // 綠色：key
            { tag: tags.string, color: '#2563eb' },        // 藍色：字串值
            { tag: tags.number, color: '#d97706' },        // 橙色：數字
            { tag: tags.bool, color: '#7c3aed' },          // 紫色：布林
            { tag: tags.null, color: '#6b7280' },          // 灰色：null
        ]);

        const state = EditorState.create({
            doc: value,
            extensions: [
                history(),
                keymap.of([...defaultKeymap, ...historyKeymap, ...closeBracketsKeymap]),
                closeBrackets(),
                updateListener,
                theme,
                cmPlaceholder(placeholder),
                json(),
                syntaxHighlighting(jsonHighlightStyle),
                jsonLinter,
                lintGutter(),
                EditorView.lineWrapping,
            ],
        });

        const view = new EditorView({
            state,
            parent: containerRef.current,
        });

        viewRef.current = view;

        return () => {
            view.destroy();
            viewRef.current = null;
        };
    }, []);

    // 外部 value 變更時同步
    useEffect(() => {
        const view = viewRef.current;
        if (view && view.state.doc.toString() !== value) {
            isExternalUpdate.current = true;
            view.dispatch({
                changes: {
                    from: 0,
                    to: view.state.doc.length,
                    insert: value,
                },
            });
            isExternalUpdate.current = false;
        }
    }, [value]);

    // 格式化 JSON
    const formatJson = useCallback(() => {
        const view = viewRef.current;
        if (view) {
            const text = view.state.doc.toString();
            try {
                const parsed = JSON.parse(text);
                const formatted = JSON.stringify(parsed, null, 2);
                view.dispatch({
                    changes: {
                        from: 0,
                        to: view.state.doc.length,
                        insert: formatted,
                    },
                });
            } catch {
                // 無法格式化，忽略
            }
        }
    }, []);

    // 掛載到 ref
    useEffect(() => {
        if (containerRef.current) {
            (containerRef.current as any).formatJson = formatJson;
        }
    }, [formatJson]);

    return (
        <div
            ref={containerRef}
            className={className}
            style={{
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                overflow: 'hidden',
                background: '#fafafa',
                ...style,
            }}
        />
    );
};

export default JsonEditor;
