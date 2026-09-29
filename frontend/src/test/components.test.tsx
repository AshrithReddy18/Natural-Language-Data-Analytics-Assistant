import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnalysisView } from '@/components/chat/AnalysisView'
import { QueryProgress } from '@/components/chat/QueryProgress'
import { ResultTable } from '@/components/data/ResultTable'
import type { StepState } from '@/store/chat'
import type { AnalysisResult, StepId } from '@/types/api'
import { monthlyAnalysis } from './fixtures'
import { renderWithProviders } from './render'

describe('AnalysisView', () => {
  it('shows KPIs, chart, insight and collapsible SQL/data sections', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AnalysisView analysis={monthlyAnalysis} />)

    expect(screen.getByText('Total revenue')).toBeInTheDocument()
    expect(screen.getByText('46.3%')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Line chart: Monthly revenue, 2025/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Key insight' })).toHaveTextContent('Revenue peaked in 2025-03')
    expect(screen.getByText('Numbers verified')).toBeInTheDocument()

    // SQL is collapsed by default; expanding shows the validated SQL and the repaired attempt.
    const sqlToggle = screen.getByRole('button', { name: /Generated SQL/ })
    expect(sqlToggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(sqlToggle)
    expect(screen.getByText('Validated read-only')).toBeInTheDocument()
    expect(screen.getAllByLabelText('SQL query')[0]).toHaveTextContent('LIMIT 1000')
    expect(screen.getByText(/Self-corrected after 1 failed attempt/)).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'As generated' }))
    expect(screen.getAllByLabelText('SQL query')[0]).toHaveTextContent('sales_amount')

    await user.click(screen.getByRole('button', { name: /Data table/ }))
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(4)
  })

  it('renders an error with a retry action', async () => {
    const onRetry = vi.fn()
    const analysis: AnalysisResult = {
      ...monthlyAnalysis,
      status: 'error',
      result: null,
      chart: null,
      kpis: [],
      insight: null,
      error: { code: 'query_timeout', message: 'The query exceeded the 15s time limit and was cancelled.' },
    }
    renderWithProviders(<AnalysisView analysis={analysis} onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('The query took too long')
    await userEvent.click(screen.getByRole('button', { name: /Try again/ }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('offers clarification options that send an answer', async () => {
    const onAnswer = vi.fn()
    const analysis: AnalysisResult = {
      ...monthlyAnalysis,
      status: 'clarification',
      sql: null,
      result: null,
      chart: null,
      kpis: [],
      insight: null,
      clarification: { question: 'Which revenue do you mean — gross or net?', options: ['Gross revenue', 'Net revenue'] },
    }
    renderWithProviders(<AnalysisView analysis={analysis} onAnswer={onAnswer} />)
    expect(screen.getByText(/gross or net/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Net revenue' }))
    expect(onAnswer).toHaveBeenCalledWith('Net revenue')
  })

  it('explains an empty result', () => {
    renderWithProviders(
      <AnalysisView analysis={{ ...monthlyAnalysis, status: 'empty', result: { ...monthlyAnalysis.result!, rows: [], row_count: 0 }, chart: null, kpis: [], insight: null }} />,
    )
    expect(screen.getByText('No records matched the requested criteria')).toBeInTheDocument()
  })
})

describe('QueryProgress', () => {
  it('shows each pipeline step with its state', () => {
    const steps = {
      understand: { status: 'done', detail: null, notes: [] },
      schema: { status: 'done', detail: '5 of 5 tables in context', notes: [] },
      generate: { status: 'done', detail: null, notes: [] },
      validate: { status: 'done', detail: null, notes: ["Column 'x' could not be resolved"] },
      execute: { status: 'running', detail: null, notes: [] },
      visualize: { status: 'pending', detail: null, notes: [] },
      insight: { status: 'pending', detail: null, notes: [] },
    } satisfies Record<StepId, StepState>
    renderWithProviders(<QueryProgress steps={steps} />)
    expect(screen.getByText('Running query', { selector: 'span' })).toHaveClass('font-medium')
    expect(screen.getByText(/5 of 5 tables/)).toBeInTheDocument()
    expect(screen.getByText(/Corrected: Column 'x'/)).toBeInTheDocument()
    expect(screen.getByText('Preparing visualization')).toHaveClass('text-subtle')
  })
})

describe('ResultTable', () => {
  it('sorts by column and paginates', async () => {
    const user = userEvent.setup()
    const rows = Array.from({ length: 30 }, (_, i) => [`City ${i}`, i * 10])
    renderWithProviders(
      <ResultTable
        currency="INR"
        result={{
          columns: [
            { name: 'city', kind: 'categorical', format: 'text', distinct_count: 30, null_count: 0 },
            { name: 'orders', kind: 'numeric', format: 'integer', distinct_count: 30, null_count: 0 },
          ],
          rows,
          row_count: 30,
          truncated: false,
          execution_ms: 3,
        }}
      />,
    )
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'orders' }))
    const firstRow = screen.getAllByRole('row')[1]
    expect(firstRow).toHaveTextContent('City 29')
    expect(screen.getByRole('columnheader', { name: /orders/ })).toHaveAttribute('aria-sort', 'descending')
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  })
})
