
import React, { useState } from 'react';
import { Send, Image as ImageIcon, Trash2, Loader2, Bug, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const BugReportPage = () => {
    const { } = useAuth();
    const [description, setDescription] = useState('');
    const [image, setImage] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [errorMessage, setErrorMessage] = useState('');

    const handlePaste = (e: React.ClipboardEvent) => {
        const items = e.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                if (blob) {
                    setImage(blob);
                    setPreviewUrl(URL.createObjectURL(blob));
                    e.preventDefault(); // Prevent double paste behavior if cursor is in image area
                }
            }
        }
    };

    const handleImageRemove = () => {
        setImage(null);
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            setPreviewUrl(null);
        }
    };

    const handleSubmit = async () => {
        if (!description.trim()) return;

        setSubmitting(true);
        setStatus('idle');
        setErrorMessage('');

        const formData = new FormData();
        formData.append('description', description);
        if (image) {
            formData.append('image', image);
        }

        try {
            await apiClient.post('/api/report', formData);
            setStatus('success');
            setDescription('');
            handleImageRemove();
        } catch (error: any) {
            setStatus('error');
            setErrorMessage(error.response?.data?.detail || '發送失敗，請稍後再試');
            console.error(error);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="bg-[#F5F5F7] min-h-full flex flex-col p-8 font-sans">
            <div className="relative z-10 w-full max-w-3xl mx-auto my-auto">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                    <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '14px',
                        background: 'linear-gradient(135deg, #eef4fd 0%, #dbeafe 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        <Bug size={24} color="#137fec" />
                    </div>
                    <div>
                        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#1f2937', margin: 0 }}>
                            回報與升等申請
                        </h1>
                        <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '14px' }}>
                            遇到問題或有功能建議？歡迎隨時回報給開發團隊。
                        </p>
                    </div>
                </div>

                <Card>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

                        {/* Status Messages */}
                        {status === 'success' && (
                            <div style={{
                                padding: '12px 16px',
                                backgroundColor: '#ecfdf5',
                                border: '1px solid #a7f3d0',
                                borderRadius: '8px',
                                color: '#065f46',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                fontSize: '14px'
                            }}>
                                <CheckCircle2 size={16} />
                                <span>回報已成功發送！我們會盡快處理。</span>
                            </div>
                        )}
                        {status === 'error' && (
                            <div style={{
                                padding: '12px 16px',
                                backgroundColor: '#fef2f2',
                                border: '1px solid #fecaca',
                                borderRadius: '8px',
                                color: '#991b1b',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                fontSize: '14px'
                            }}>
                                <AlertCircle size={16} />
                                <span>{errorMessage}</span>
                            </div>
                        )}

                        <div>
                            <label style={{
                                display: 'block',
                                fontSize: '14px',
                                fontWeight: 600,
                                color: '#374151',
                                marginBottom: '6px'
                            }}>
                                狀況描述
                                <span style={{
                                    fontSize: '12px',
                                    fontWeight: 400,
                                    color: '#6b7280',
                                    marginLeft: '8px',
                                    backgroundColor: '#f3f4f6',
                                    padding: '2px 8px',
                                    borderRadius: '4px'
                                }}>
                                    支援 Ctrl+V 貼上截圖
                                </span>
                            </label>
                            <textarea
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                onPaste={handlePaste}
                                placeholder="請在此詳細描述您遇到的問題，或是期望的新功能..."
                                style={{
                                    width: '100%',
                                    minHeight: '150px',
                                    padding: '12px',
                                    border: '1px solid #d1d5db',
                                    borderRadius: '8px',
                                    fontSize: '14px',
                                    lineHeight: '1.5',
                                    resize: 'vertical',
                                    outline: 'none',
                                    transition: 'border-color 0.2s',
                                }}
                                onFocus={(e) => e.target.style.borderColor = '#3b82f6'}
                                onBlur={(e) => e.target.style.borderColor = '#d1d5db'}
                                disabled={submitting}
                            />
                        </div>

                        {/* Image Preview */}
                        {image && (
                            <div style={{
                                position: 'relative',
                                padding: '16px',
                                backgroundColor: '#f9fafb',
                                border: '1px dashed #d1d5db',
                                borderRadius: '8px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '16px'
                            }}>
                                <div style={{
                                    width: '80px',
                                    height: '80px',
                                    borderRadius: '6px',
                                    overflow: 'hidden',
                                    border: '1px solid #e5e7eb',
                                    backgroundColor: '#fff',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
                                }}>
                                    {previewUrl ? (
                                        <img
                                            src={previewUrl}
                                            alt="Preview"
                                            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                                        />
                                    ) : (
                                        <ImageIcon size={24} color="#9ca3af" />
                                    )}
                                </div>
                                <div style={{ flex: 1 }}>
                                    <p style={{ margin: 0, fontSize: '14px', fontWeight: 500, color: '#374151' }}>
                                        {image.name}
                                    </p>
                                    <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#6b7280' }}>
                                        {(image.size / 1024).toFixed(1)} KB
                                    </p>
                                </div>
                                <Button
                                    variant="danger"
                                    size="sm"
                                    onClick={handleImageRemove}
                                    disabled={submitting}
                                >
                                    <Trash2 size={16} />
                                </Button>
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                            <Button
                                variant="primary"
                                onClick={handleSubmit}
                                disabled={submitting || !description.trim()}
                                style={{ minWidth: '120px' }}
                            >
                                {submitting ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" style={{ marginRight: '8px' }} />
                                        發送中...
                                    </>
                                ) : (
                                    <>
                                        <Send size={16} style={{ marginRight: '8px' }} />
                                        確認發送
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
};

export default BugReportPage;
