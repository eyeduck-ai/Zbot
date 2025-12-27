
import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    title?: string;
    footer?: React.ReactNode;
    noPadding?: boolean;
}

export const Card = ({ title, children, style, className, footer, noPadding, ...props }: CardProps) => {
    return (
        <div
            {...props}
            style={{
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-md)',
                border: '1px solid rgba(0,0,0,0.04)',
                overflow: 'hidden',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                ...style
            }}
            className={className}
        >
            {title && (
                <div style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600 }}>{title}</h3>
                </div>
            )}
            {noPadding ? children : (
                <div style={{ padding: '20px' }}>
                    {children}
                </div>
            )}
            {footer && (
                <div style={{
                    padding: '16px 20px',
                    borderTop: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-app)' // Subtle contrast for footer
                }}>
                    {footer}
                </div>
            )}
        </div>
    );
};
