/**
 * CodeMirror Editor Component
 * 
 * 基於 CodeMirror 6 的編輯器元件，支援：
 * - 原生 Undo/Redo (⌘Z / ⌘Shift+Z)
 * - 精確的拖曳插入定位
 * - 自訂佔位符語法高亮
 */

import { useEffect, useRef, useCallback } from 'react';
import { EditorState } from '@codemirror/state';
import { EditorView, keymap, placeholder as cmPlaceholder, dropCursor } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';

interface CodeMirrorEditorProps {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    className?: string;
    style?: React.CSSProperties;
    onFocus?: () => void;
    onBlur?: () => void;
}

export const CodeMirrorEditor = ({
    value,
    onChange,
    placeholder = '',
    className = '',
    style = {},
    onFocus,
    onBlur,
}: CodeMirrorEditorProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewRef = useRef<EditorView | null>(null);
    const isExternalUpdate = useRef(false);

    // 初始化編輯器
    useEffect(() => {
        if (!containerRef.current) return;

        const updateListener = EditorView.updateListener.of((update) => {
            if (update.docChanged && !isExternalUpdate.current) {
                onChange(update.state.doc.toString());
            }
        });

        const focusListener = EditorView.focusChangeEffect.of((_, focusing) => {
            if (focusing) {
                onFocus?.();
            } else {
                onBlur?.();
            }
            return null;
        });

        const theme = EditorView.theme({
            '&': {
                height: '100%',
                fontSize: '13px',
                fontFamily: 'monospace',
            },
            '.cm-content': {
                padding: '16px',
                minHeight: '400px',
                caretColor: '#3b82f6',
            },
            '.cm-focused': {
                outline: 'none',
            },
            '.cm-line': {
                lineHeight: '1.6',
            },
            '.cm-cursor': {
                borderLeftColor: '#3b82f6',
                borderLeftWidth: '3px',  // 更粗的游標
            },
            '.cm-dropCursor': {
                borderLeftColor: '#ef4444',  // 拖曳指示器用紅色
                borderLeftWidth: '3px',
            },
            '.cm-placeholder': {
                color: '#9ca3af',
            },
            // 佔位符高亮
            '.cm-placeholder-var': {
                color: '#3b82f6',
                fontWeight: '500',
            },
        });

        const state = EditorState.create({
            doc: value,
            extensions: [
                history(),
                keymap.of([...defaultKeymap, ...historyKeymap]),
                updateListener,
                focusListener,
                theme,
                cmPlaceholder(placeholder),
                dropCursor(),
                EditorView.lineWrapping,
                // 允許拖放
                EditorView.domEventHandlers({
                    drop: (event, view) => {
                        const text = event.dataTransfer?.getData('text/plain');
                        if (text && text.startsWith('$')) {
                            event.preventDefault();
                            const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
                            if (pos !== null) {
                                view.dispatch({
                                    changes: { from: pos, insert: text },
                                    selection: { anchor: pos + text.length },
                                });
                            }
                            return true;
                        }
                        return false;
                    },
                    dragover: (event) => {
                        event.preventDefault();
                        return false;
                    },
                }),
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
    }, []); // 只在 mount 時初始化

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

    // 暴露插入方法
    const insertText = useCallback((text: string) => {
        const view = viewRef.current;
        if (view) {
            const pos = view.state.selection.main.head;
            view.dispatch({
                changes: { from: pos, insert: text },
                selection: { anchor: pos + text.length },
            });
            view.focus();
        }
    }, []);

    // 將 insertText 掛載到 ref 上供外部使用
    useEffect(() => {
        if (containerRef.current) {
            (containerRef.current as any).insertText = insertText;
        }
    }, [insertText]);

    return (
        <div
            ref={containerRef}
            className={className}
            style={{
                border: '2px dashed #d1d5db',
                borderRadius: '8px',
                overflow: 'hidden',
                ...style,
            }}
        />
    );
};

export default CodeMirrorEditor;
