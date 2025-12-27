
import React from 'react';

interface BadgeProps {
    children: React.ReactNode;
    variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
    className?: string;
}

export const Badge = ({ children, variant = 'neutral', className }: BadgeProps) => {
    const getStyle = (): React.CSSProperties => {
        const base = {
            display: 'inline-flex',
            alignItems: 'center',
            padding: '4px 10px',
            borderRadius: '20px',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase' as const,
            letterSpacing: '0.05em',
        };

        switch (variant) {
            case 'success':
                return { ...base, backgroundColor: 'rgba(52, 199, 89, 0.15)', color: '#248A3D' };
            case 'warning':
                return { ...base, backgroundColor: 'rgba(255, 149, 0, 0.15)', color: '#CC7700' };
            case 'error':
                return { ...base, backgroundColor: 'rgba(255, 59, 48, 0.15)', color: '#CC2F26' };
            case 'info':
                return { ...base, backgroundColor: 'rgba(0, 122, 255, 0.15)', color: '#0062CC' };
            case 'neutral':
            default:
                return { ...base, backgroundColor: 'rgba(142, 142, 147, 0.15)', color: '#636366' };
        }
    };

    return (
        <span style={getStyle()} className={className}>
            {children}
        </span>
    );
};
