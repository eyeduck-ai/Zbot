
import React from 'react';
import { Check, Shield, Star, Crown, Info } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';

interface Plan {
    id: string;
    name: string;
    price: string;
    description: string;
    features: string[];
    bg: string;
    icon: React.ReactNode;
    color: string;
}

export const PricingPage = ({ onNavigate }: { onNavigate?: (path: string) => void }) => {
    const { role } = useAuth();

    // 定義方案
    const PLANS: Plan[] = [
        {
            id: 'basic_0',
            name: '初心者 Lv.0',
            price: 'Free',
            description: '訪客瀏覽權限',
            features: [
                '僅能登入系統',
                '無任何工具使用權限',
                '需申請開通權限'
            ],
            bg: 'linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%)',
            icon: <Info size={24} />,
            color: '#6b7280',
        },
        {
            id: 'basic_1',
            name: '初心者 Lv.1',
            price: '基礎版',
            description: '基本的門診與病歷工具',
            features: [
                'IVI 紀錄工具',
                '門診系統開單 (測試中)',
                '健保事審 (測試中)'
            ],
            bg: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)',
            icon: <Shield size={24} />,
            color: '#4f46e5',
        },
        {
            id: 'basic_2',
            name: '奴工',
            price: '進階版',
            description: '解鎖手術相關功能',
            features: [
                '包含 Lv.1 所有功能',
                '手術紀錄工具',
                '門診系統組套設定'
            ],
            bg: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)',
            icon: <Star size={24} />,
            color: '#059669',
        },
        {
            id: 'cr',
            name: 'CR / VS',
            price: '專業版',
            description: '完整的管理與統計權限',
            features: [
                '包含所有功能',
                '待床追蹤看板',
                '手術統計報表',
                '收費碼統計報表'
            ],
            bg: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
            icon: <Crown size={24} />,
            color: '#d97706',
        }
    ];

    // 判斷目前使用者的方案
    const currentPlanId = role || 'basic_0';

    return (
        <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto', fontFamily: '"Manrope", sans-serif' }}>
            {/* Header */}
            <div style={{ textAlign: 'center', marginBottom: '48px' }}>
                <h1 style={{ fontSize: '32px', fontWeight: 800, color: '#111827', marginBottom: '12px' }}>
                    選擇適合您的方案
                </h1>
                <p style={{ fontSize: '16px', color: '#6b7280', maxWidth: '600px', margin: '0 auto' }}>
                    Zbot 提供不同層級的工具權限，協助您在臨床工作中更有效率。
                </p>
            </div>

            {/* Plans Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '24px',
                alignItems: 'stretch'
            }}>
                {PLANS.map(plan => {
                    const isCurrent = currentPlanId === plan.id;

                    return (
                        <Card key={plan.id} style={{
                            padding: '0',
                            overflow: 'hidden',
                            border: isCurrent ? `2px solid ${plan.color}` : '1px solid #e5e7eb',
                            display: 'flex',
                            flexDirection: 'column',
                            position: 'relative',
                            transition: 'transform 0.2s, box-shadow 0.2s',
                        }}
                            className="hover:shadow-lg hover:-translate-y-1 transition-all duration-200"
                        >
                            {isCurrent && (
                                <div style={{
                                    position: 'absolute',
                                    top: '12px',
                                    right: '12px',
                                    backgroundColor: plan.color,
                                    color: 'white',
                                    padding: '4px 10px',
                                    borderRadius: '20px',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                                }}>
                                    <Check size={12} />
                                    目前方案
                                </div>
                            )}

                            {/* Plan Header */}
                            <div style={{
                                padding: '32px 24px',
                                background: plan.bg,
                                borderBottom: '1px solid rgba(0,0,0,0.05)'
                            }}>
                                <div style={{
                                    width: '48px',
                                    height: '48px',
                                    borderRadius: '12px',
                                    backgroundColor: 'white',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: plan.color,
                                    marginBottom: '16px',
                                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                                }}>
                                    {plan.icon}
                                </div>
                                <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#1f2937', marginBottom: '4px' }}>
                                    {plan.name}
                                </h3>
                                <div style={{ fontSize: '14px', color: '#6b7280', fontWeight: 500 }}>
                                    {plan.description}
                                </div>
                            </div>

                            {/* Plan Features */}
                            <div style={{ padding: '24px', flex: 1, display: 'flex', flexDirection: 'column' }}>
                                <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px 0', flex: 1 }}>
                                    {plan.features.map((feature, idx) => (
                                        <li key={idx} style={{
                                            display: 'flex',
                                            alignItems: 'flex-start',
                                            gap: '12px',
                                            marginBottom: '12px',
                                            fontSize: '14px',
                                            color: '#374151'
                                        }}>
                                            <div style={{
                                                minWidth: '16px',
                                                height: '16px',
                                                marginTop: '3px',
                                                borderRadius: '50%',
                                                backgroundColor: isCurrent ? '#ecfdf5' : '#f3f4f6',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center'
                                            }}>
                                                <Check size={10} color={isCurrent ? '#059669' : '#9ca3af'} />
                                            </div>
                                            {feature}
                                        </li>
                                    ))}
                                </ul>

                                <Button
                                    variant={isCurrent ? 'secondary' : 'primary'}
                                    disabled={isCurrent}
                                    onClick={() => {
                                        // 導向回報頁面
                                        if (onNavigate) {
                                            onNavigate('bug_report');
                                        } else {
                                            // Fallback default navigation if prop not provided
                                            window.location.hash = '#bug_report';
                                        }
                                    }}
                                    style={{
                                        width: '100%',
                                        backgroundColor: isCurrent ? '#f3f4f6' : plan.color,
                                        color: isCurrent ? '#9ca3af' : 'white',
                                        border: 'none'
                                    }}
                                >
                                    {isCurrent ? '使用中' : '申請變更'}
                                </Button>
                            </div>
                        </Card>
                    );
                })}
            </div>

            {/* Application Info */}
            <div style={{ marginTop: '48px', textAlign: 'center', color: '#6b7280', fontSize: '14px' }}>
                <p>需要變更方案權限？請點擊上方按鈕前往「升等申請」頁面填寫需求。</p>
            </div>
        </div>
    );
};

export default PricingPage;
