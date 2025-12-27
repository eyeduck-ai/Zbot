/**
 * StepIndicator - 步驟進度條元件
 * 
 * 共用元件，用於顯示多步驟流程的進度狀態。
 * 支援點擊返回已完成的步驟。
 * 
 * @example
 * const STEPS = [
 *     { id: 'fetch', label: '抓取排程' },
 *     { id: 'edit', label: '確認編輯' },
 *     { id: 'done', label: '完成' },
 * ];
 * 
 * <StepIndicator
 *     steps={STEPS}
 *     currentStepId="edit"
 *     onStepClick={(stepId) => setCurrentStep(stepId)}
 *     disableNavigation={currentStep === 'done'}
 * />
 */

import React from 'react';
import { Check } from 'lucide-react';
import { THEME } from '../styles/theme';

// =============================================================================
// Types
// =============================================================================

export interface StepDefinition {
    id: string;
    label: string;
}

export interface StepIndicatorProps {
    /** 步驟定義陣列 */
    steps: StepDefinition[];
    /** 目前步驟的 ID */
    currentStepId: string;
    /** 點擊步驟時的回呼函數 */
    onStepClick?: (stepId: string) => void;
    /** 是否禁用導航（例如在最終步驟時） */
    disableNavigation?: boolean;
    /** 額外的 className */
    className?: string;
}

// =============================================================================
// Component
// =============================================================================

export const StepIndicator: React.FC<StepIndicatorProps> = ({
    steps,
    currentStepId,
    onStepClick,
    disableNavigation = false,
    className = '',
}) => {
    const currentStepIndex = steps.findIndex(s => s.id === currentStepId);

    return (
        <div className={`flex items-center gap-2 bg-white/50 backdrop-blur-xl rounded-2xl p-3 border border-white/40 shadow-lg ${className}`}>
            {steps.map((step, i) => {
                const isActive = step.id === currentStepId;
                const isComplete = i < currentStepIndex;
                const isClickable = i < currentStepIndex && !disableNavigation && onStepClick;

                return (
                    <React.Fragment key={step.id}>
                        <button
                            onClick={() => isClickable && onStepClick(step.id)}
                            disabled={!isClickable}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl transition-all"
                            style={{
                                backgroundColor: isActive ? THEME.primary : isComplete ? THEME.successLight : '#f3f4f6',
                                color: isActive ? 'white' : isComplete ? THEME.success : '#9ca3af',
                                cursor: isClickable ? 'pointer' : 'default',
                                boxShadow: isActive ? '0 4px 6px -1px rgba(19, 127, 236, 0.3)' : 'none',
                            }}
                        >
                            <span
                                className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                                style={{
                                    backgroundColor: isActive ? 'rgba(255,255,255,0.2)' : isComplete ? THEME.success : '#e5e7eb',
                                    color: isComplete ? 'white' : 'inherit',
                                }}
                            >
                                {isComplete ? <Check size={14} /> : i + 1}
                            </span>
                            <span className="font-medium text-sm">{step.label}</span>
                        </button>
                        {i < steps.length - 1 && (
                            <div
                                className="flex-1 h-0.5"
                                style={{ backgroundColor: i < currentStepIndex ? THEME.success : '#e5e7eb' }}
                            />
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
};

export default StepIndicator;
