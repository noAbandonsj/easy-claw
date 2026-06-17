import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CapabilityDialog } from './CapabilityDialogs';

describe('CapabilityDialog', () => {
  it('renders skills data', () => {
    render(
      <CapabilityDialog
        kind="skills"
        payload={{
          source_count: 1,
          skill_count: 2,
          sources: [
            {
              scope: 'project',
              label: 'project skills',
              skill_count: 2,
              backend_path: '/skills/',
              filesystem_path: 'D:\\Pathon\\Programs\\easy-claw\\skills',
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Skill 来源' })).toBeInTheDocument();
    expect(screen.getByText('project skills')).toBeInTheDocument();
  });

  it('renders slash command help', () => {
    render(
      <CapabilityDialog
        kind="help"
        payload={[{ name: '/skills', description: '查看 Skill', usage: '/skills' }]}
      />,
    );

    expect(screen.getByRole('heading', { name: '可用命令' })).toBeInTheDocument();
    expect(screen.getAllByText('/skills')).toHaveLength(2);
  });
});
