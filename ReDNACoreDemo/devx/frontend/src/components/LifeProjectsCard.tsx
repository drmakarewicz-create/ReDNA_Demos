/**
 * Life OS Projects Card - Phase 2
 *
 * Shows top active projects with progress bars and next steps.
 * Includes expandable Priority Matrix view for organizing todos.
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Grid3x3, AlertCircle, Target } from 'lucide-react';

interface Project {
  id: string;
  title: string;
  goal_id?: string;
  quadrant: string;
  status: string;
  next_step?: string;
  risk?: string;
  confidence: number;
  created_at?: string;
  updated_at?: string;
}

interface PriorityMatrix {
  important_urgent: string[];
  important_not_urgent: string[];
  not_important_urgent: string[];
  neither: string[];
}

interface Todo {
  id: string;
  text: string;
  status: string;
  priority?: string;
}

interface LifeProjectsCardProps {
  userId: string;
  baseUrl: string;
}

const QUADRANT_COLORS = {
  important_urgent: 'border-orange-500 bg-orange-50',
  important_not_urgent: 'border-green-500 bg-green-50',
  not_important_urgent: 'border-yellow-500 bg-yellow-50',
  neither: 'border-gray-400 bg-gray-50'
};

const QUADRANT_LABELS = {
  important_urgent: 'Important & Urgent',
  important_not_urgent: 'Important & Not Urgent',
  not_important_urgent: 'Not Important & Urgent',
  neither: 'Neither'
};

export default function LifeProjectsCard({ userId, baseUrl }: LifeProjectsCardProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [matrix, setMatrix] = useState<PriorityMatrix | null>(null);
  const [todos, setTodos] = useState<Todo[]>([]);
  const [showMatrix, setShowMatrix] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
    loadTodos();
  }, [userId]);

  const loadProjects = async () => {
    try {
      const response = await fetch(`${baseUrl}/ui/hc/life/${userId}/projects/top?limit=3`);
      if (!response.ok) throw new Error('Failed to load projects');
      const data = await response.json();
      setProjects(data.projects || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const loadMatrix = async () => {
    try {
      const response = await fetch(`${baseUrl}/ui/hc/life/${userId}/matrix`);
      if (!response.ok) throw new Error('Failed to load matrix');
      const data = await response.json();
      setMatrix(data.matrix);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load matrix');
    }
  };

  const loadTodos = async () => {
    try {
      const response = await fetch(`${baseUrl}/ui/hc/life/${userId}/todos?status=active`);
      if (!response.ok) throw new Error('Failed to load todos');
      const data = await response.json();
      setTodos(data.todos || []);
    } catch (err) {
      console.error('Failed to load todos:', err);
    }
  };

  const handleOpenMatrix = () => {
    if (!matrix) {
      loadMatrix();
    }
    setShowMatrix(true);
  };

  const handleDragStart = (e: React.DragEvent, todoId: string) => {
    e.dataTransfer.setData('todoId', todoId);
  };

  const handleDrop = async (e: React.DragEvent, quadrant: string) => {
    e.preventDefault();
    const todoId = e.dataTransfer.getData('todoId');

    try {
      const response = await fetch(`${baseUrl}/ui/hc/life/${userId}/matrix`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ todo_id: todoId, quadrant })
      });

      if (!response.ok) throw new Error('Failed to update matrix');

      // Reload matrix
      await loadMatrix();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update matrix');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const getProgressColor = (confidence: number) => {
    if (confidence >= 0.7) return 'bg-green-500';
    if (confidence >= 0.4) return 'bg-yellow-500';
    return 'bg-orange-500';
  };

  const getTodoById = (todoId: string) => {
    return todos.find(t => t.id === todoId);
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Projects</h3>
        </div>
        <div className="text-sm text-gray-500">Loading projects...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-red-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <h3 className="font-semibold text-gray-900">Projects</h3>
        </div>
        <div className="text-sm text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Projects</h3>
        </div>
        <button
          onClick={handleOpenMatrix}
          className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          <Grid3x3 className="w-4 h-4" />
          Matrix
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="text-sm text-gray-500 py-2">
          No active projects yet. Projects help organize your goals and todos.
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map(project => (
            <div
              key={project.id}
              className={`border-l-4 ${QUADRANT_COLORS[project.quadrant as keyof typeof QUADRANT_COLORS] || 'border-gray-300'} pl-3 py-2`}
            >
              <div className="flex items-start justify-between mb-1">
                <h4 className="font-medium text-gray-900 text-sm">{project.title}</h4>
                <span className="text-xs text-gray-500">
                  {Math.round(project.confidence * 100)}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
                <div
                  className={`h-1.5 rounded-full ${getProgressColor(project.confidence)}`}
                  style={{ width: `${project.confidence * 100}%` }}
                />
              </div>

              {project.next_step && (
                <div className="text-xs text-gray-600">
                  Next: {project.next_step}
                </div>
              )}

              {project.risk && (
                <div className="text-xs text-orange-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {project.risk}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Priority Matrix Modal */}
      {showMatrix && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Priority Matrix</h2>
              <button
                onClick={() => setShowMatrix(false)}
                className="text-gray-500 hover:text-gray-700 text-xl"
              >
                ×
              </button>
            </div>

            <div className="p-4">
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(QUADRANT_LABELS).map(([key, label]) => (
                  <div
                    key={key}
                    className={`border-2 rounded-lg p-4 min-h-[200px] ${QUADRANT_COLORS[key as keyof typeof QUADRANT_COLORS]}`}
                    onDrop={(e) => handleDrop(e, key)}
                    onDragOver={handleDragOver}
                  >
                    <h3 className="font-semibold text-gray-900 mb-3 text-sm">
                      {label}
                    </h3>

                    <div className="space-y-2">
                      {matrix && matrix[key as keyof PriorityMatrix]?.map(todoId => {
                        const todo = getTodoById(todoId);
                        if (!todo) return null;

                        return (
                          <div
                            key={todoId}
                            draggable
                            onDragStart={(e) => handleDragStart(e, todoId)}
                            className="bg-white border border-gray-300 rounded p-2 text-sm cursor-move hover:shadow-md transition-shadow"
                          >
                            {todo.text}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 text-xs text-gray-500">
                Drag and drop todos between quadrants to organize by priority.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
