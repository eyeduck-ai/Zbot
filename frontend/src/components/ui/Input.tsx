
import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    helperText?: string;
}

export const Input = ({ label, error, helperText, style, className, ...props }: InputProps) => {
    return (
        <div style={{ marginBottom: '16px', width: '100%' }}>
            {label && (
                <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: 500,
                    color: 'var(--text-primary)',
                    marginBottom: '6px',
                    marginLeft: '2px'
                }}>
                    {label}
                </label>
            )}
            <input
                {...props}
                style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: '14px',
                    borderRadius: '8px',
                    border: `1px solid ${error ? 'var(--accent-red)' : 'var(--border-light)'}`,
                    backgroundColor: 'var(--bg-card)',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                    ...style
                }}
                onFocus={(e) => {
                    if (!error) {
                        e.currentTarget.style.borderColor = 'var(--accent-blue)';
                        e.currentTarget.style.boxShadow = '0 0 0 3px rgba(0, 122, 255, 0.15)';
                    }
                }}
                onBlur={(e) => {
                    if (!error) {
                        e.currentTarget.style.borderColor = 'var(--border-light)';
                        e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.02)';
                    }
                }}
                className={className}
            />
            {error && (
                <p style={{ fontSize: '12px', color: 'var(--accent-red)', marginTop: '4px', marginLeft: '2px' }}>
                    {error}
                </p>
            )}
            {helperText && !error && (
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', marginLeft: '2px' }}>
                    {helperText}
                </p>
            )}
        </div>
    );
};
