
import React from 'react';
import { Construction } from 'lucide-react';

interface PlaceholderPageProps {
    title: string;
    description?: string;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ title, description = '此功能建置中，敬請期待' }) => {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#6b7280',
            backgroundColor: '#fff',
            margin: '20px',
            borderRadius: '12px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
        }}>
            <div style={{
                padding: '24px',
                backgroundColor: '#f3f4f6',
                borderRadius: '50%',
                marginBottom: '24px'
            }}>
                <Construction size={48} color="#9ca3af" />
            </div>
            <h2 style={{
                margin: '0 0 12px 0',
                fontSize: '24px',
                fontWeight: 600,
                color: '#1f2937'
            }}>
                {title}
            </h2>
            <p style={{
                margin: 0,
                fontSize: '16px',
                color: '#6b7280'
            }}>
                {description}
            </p>
        </div>
    );
};
