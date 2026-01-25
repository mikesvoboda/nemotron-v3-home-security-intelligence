/**
 * PropertyManagement - Settings component for managing properties and areas.
 *
 * Provides CRUD operations for:
 * - Properties (physical locations within a household)
 * - Areas (logical zones within a property)
 *
 * Features:
 * - Accordion/collapsible property sections
 * - Nested area management within each property
 * - Camera count display per area
 * - Navigation to AreaCameraLinking for camera assignment
 *
 * @see NEM-3135 - Phase 7.2: Create PropertyManagement component
 */

import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock,
  Edit2,
  Globe,
  Loader2,
  MapPin,
  Plus,
  Trash2,
  Video,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import {
  usePropertiesQuery,
  useAreasQuery,
  useAreaCamerasQuery,
  usePropertyMutations,
  useAreaMutations,
  type PropertyResponse,
  type PropertyCreate,
  type PropertyUpdate,
  type AreaResponse,
  type AreaCreate,
  type AreaUpdate,
} from '../../hooks/usePropertyQueries';
import { ErrorState } from '../common';

// =============================================================================
// Types
// =============================================================================

interface PropertyFormData {
  name: string;
  address: string;
  timezone: string;
}

interface PropertyFormErrors {
  name?: string;
  address?: string;
  timezone?: string;
}

interface AreaFormData {
  name: string;
  description: string;
  color: string;
}

interface AreaFormErrors {
  name?: string;
  description?: string;
  color?: string;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_PROPERTY_FORM: PropertyFormData = {
  name: '',
  address: '',
  timezone: 'UTC',
};

const DEFAULT_AREA_FORM: AreaFormData = {
  name: '',
  description: '',
  color: '#76B900',
};

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Phoenix',
  'America/Anchorage',
  'Pacific/Honolulu',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Australia/Sydney',
];

const AREA_COLORS = [
  { value: '#76B900', label: 'NVIDIA Green' },
  { value: '#3B82F6', label: 'Blue' },
  { value: '#8B5CF6', label: 'Purple' },
  { value: '#EF4444', label: 'Red' },
  { value: '#F59E0B', label: 'Amber' },
  { value: '#10B981', label: 'Emerald' },
  { value: '#EC4899', label: 'Pink' },
  { value: '#6366F1', label: 'Indigo' },
];

// =============================================================================
// Sub-components
// =============================================================================

interface AreaCameraCountProps {
  areaId: number;
}

function AreaCameraCount({ areaId }: AreaCameraCountProps) {
  const { count, isLoading } = useAreaCamerasQuery({ areaId });

  if (isLoading) {
    return <span className="text-xs text-gray-500">...</span>;
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs',
        count > 0 ? 'bg-primary/10 text-primary' : 'bg-gray-800 text-gray-500'
      )}
      data-testid={`area-camera-count-${areaId}`}
    >
      <Video className="h-3 w-3" />
      {count}
    </span>
  );
}

interface AreaListProps {
  propertyId: number;
  onEditArea: (area: AreaResponse) => void;
  onDeleteArea: (area: AreaResponse) => void;
  onAddArea: () => void;
}

function AreaList({ propertyId, onEditArea, onDeleteArea, onAddArea }: AreaListProps) {
  const { areas, isLoading, isError, error, refetch } = useAreasQuery({ propertyId });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4 text-gray-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading areas...
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        title="Failed to load areas"
        message={error}
        onRetry={() => void refetch()}
        variant="compact"
        testId={`area-list-error-${propertyId}`}
      />
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-gray-700 bg-[#121212]">
      <div className="flex items-center justify-between border-b border-gray-700 px-3 py-2">
        <span className="text-sm font-medium text-gray-300">Areas</span>
        <button
          onClick={onAddArea}
          className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-primary transition-colors hover:bg-primary/10"
          data-testid={`add-area-btn-property-${propertyId}`}
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>

      {areas.length === 0 ? (
        <div className="px-3 py-4 text-center text-sm text-gray-500">
          No areas defined. Add areas to organize your cameras.
        </div>
      ) : (
        <ul className="divide-y divide-gray-700" data-testid={`area-list-property-${propertyId}`}>
          {areas.map((area) => (
            <li key={area.id} className="flex items-center justify-between px-3 py-2">
              <div className="flex items-center gap-2">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: area.color }}
                  aria-hidden="true"
                />
                <span className="text-sm text-text-primary">{area.name}</span>
                <AreaCameraCount areaId={area.id} />
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onEditArea(area)}
                  className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-primary"
                  aria-label={`Edit ${area.name}`}
                  data-testid={`edit-area-${area.id}`}
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => onDeleteArea(area)}
                  className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-500"
                  aria-label={`Delete ${area.name}`}
                  data-testid={`delete-area-${area.id}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface PropertyAccordionProps {
  property: PropertyResponse;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onEditArea: (area: AreaResponse) => void;
  onDeleteArea: (area: AreaResponse) => void;
  onAddArea: () => void;
}

function PropertyAccordion({
  property,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
  onEditArea,
  onDeleteArea,
  onAddArea,
}: PropertyAccordionProps) {
  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#1A1A1A]"
      data-testid={`property-${property.id}`}
    >
      {/* Property Header */}
      <div className="flex items-center justify-between p-4">
        <button
          onClick={onToggle}
          className="flex flex-1 items-center gap-3 text-left"
          aria-expanded={isExpanded}
          data-testid={`property-toggle-${property.id}`}
        >
          {isExpanded ? (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronRight className="h-5 w-5 text-gray-400" />
          )}
          <Building2 className="h-5 w-5 text-primary" />
          <div>
            <span className="font-medium text-text-primary">{property.name}</span>
            {property.address && (
              <span className="ml-2 text-sm text-gray-500">- {property.address}</span>
            )}
          </div>
        </button>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Globe className="h-3 w-3" />
            {property.timezone}
          </div>
          <button
            onClick={onEdit}
            className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-primary"
            aria-label={`Edit ${property.name}`}
            data-testid={`edit-property-${property.id}`}
          >
            <Edit2 className="h-4 w-4" />
          </button>
          <button
            onClick={onDelete}
            className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-500"
            aria-label={`Delete ${property.name}`}
            data-testid={`delete-property-${property.id}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Property Content (Areas) */}
      {isExpanded && (
        <div className="border-t border-gray-700 p-4">
          {property.address && (
            <div className="mb-3 flex items-center gap-2 text-sm text-gray-400">
              <MapPin className="h-4 w-4" />
              {property.address}
            </div>
          )}
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Clock className="h-4 w-4" />
            Created: {new Date(property.created_at).toLocaleDateString()}
          </div>

          <AreaList
            propertyId={property.id}
            onEditArea={onEditArea}
            onDeleteArea={onDeleteArea}
            onAddArea={onAddArea}
          />
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export interface PropertyManagementProps {
  /** The household ID to manage properties for */
  householdId: number;
  /** Optional className for styling */
  className?: string;
}

/**
 * PropertyManagement component for managing properties and areas.
 *
 * Features:
 * - List properties for the household
 * - Create/Edit/Delete properties
 * - Nested area management with accordion UI
 * - Camera count per area
 */
export default function PropertyManagement({ householdId, className }: PropertyManagementProps) {
  // Query hooks
  const { properties, isLoading, isError, error, refetch } = usePropertiesQuery({
    householdId,
    enabled: householdId > 0,
  });

  // Mutation hooks
  const { createProperty, updateProperty, deleteProperty } = usePropertyMutations();
  const { createArea, updateArea, deleteArea } = useAreaMutations();

  // UI state
  const [expandedProperties, setExpandedProperties] = useState<Set<number>>(new Set());

  // Property modal state
  const [isPropertyModalOpen, setIsPropertyModalOpen] = useState(false);
  const [editingProperty, setEditingProperty] = useState<PropertyResponse | null>(null);
  const [propertyForm, setPropertyForm] = useState<PropertyFormData>(DEFAULT_PROPERTY_FORM);
  const [propertyErrors, setPropertyErrors] = useState<PropertyFormErrors>({});

  // Area modal state
  const [isAreaModalOpen, setIsAreaModalOpen] = useState(false);
  const [editingArea, setEditingArea] = useState<AreaResponse | null>(null);
  const [areaPropertyId, setAreaPropertyId] = useState<number | null>(null);
  const [areaForm, setAreaForm] = useState<AreaFormData>(DEFAULT_AREA_FORM);
  const [areaErrors, setAreaErrors] = useState<AreaFormErrors>({});

  // Delete confirmation state
  const [isDeletePropertyModalOpen, setIsDeletePropertyModalOpen] = useState(false);
  const [deletingProperty, setDeletingProperty] = useState<PropertyResponse | null>(null);
  const [isDeleteAreaModalOpen, setIsDeleteAreaModalOpen] = useState(false);
  const [deletingArea, setDeletingArea] = useState<AreaResponse | null>(null);

  // =============================================================================
  // Property Handlers
  // =============================================================================

  const toggleProperty = useCallback((propertyId: number) => {
    setExpandedProperties((prev) => {
      const next = new Set(prev);
      if (next.has(propertyId)) {
        next.delete(propertyId);
      } else {
        next.add(propertyId);
      }
      return next;
    });
  }, []);

  const handleOpenAddPropertyModal = useCallback(() => {
    setEditingProperty(null);
    setPropertyForm(DEFAULT_PROPERTY_FORM);
    setPropertyErrors({});
    setIsPropertyModalOpen(true);
  }, []);

  const handleOpenEditPropertyModal = useCallback((property: PropertyResponse) => {
    setEditingProperty(property);
    setPropertyForm({
      name: property.name,
      address: property.address ?? '',
      timezone: property.timezone,
    });
    setPropertyErrors({});
    setIsPropertyModalOpen(true);
  }, []);

  const handleClosePropertyModal = useCallback(() => {
    setIsPropertyModalOpen(false);
    setEditingProperty(null);
    setPropertyForm(DEFAULT_PROPERTY_FORM);
    setPropertyErrors({});
  }, []);

  const validatePropertyForm = useCallback((data: PropertyFormData): PropertyFormErrors => {
    const errors: PropertyFormErrors = {};
    if (!data.name.trim()) {
      errors.name = 'Property name is required';
    } else if (data.name.length > 100) {
      errors.name = 'Property name must be 100 characters or less';
    }
    if (data.address && data.address.length > 500) {
      errors.address = 'Address must be 500 characters or less';
    }
    if (!data.timezone.trim()) {
      errors.timezone = 'Timezone is required';
    }
    return errors;
  }, []);

  const handleSubmitProperty = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      const errors = validatePropertyForm(propertyForm);
      if (Object.keys(errors).length > 0) {
        setPropertyErrors(errors);
        return;
      }

      setPropertyErrors({});

      try {
        if (editingProperty) {
          const updateData: PropertyUpdate = {
            name: propertyForm.name.trim(),
            address: propertyForm.address.trim() || undefined,
            timezone: propertyForm.timezone,
          };
          await updateProperty.mutateAsync({
            propertyId: editingProperty.id,
            data: updateData,
          });
        } else {
          const createData: PropertyCreate = {
            name: propertyForm.name.trim(),
            address: propertyForm.address.trim() || undefined,
            timezone: propertyForm.timezone,
          };
          await createProperty.mutateAsync({
            householdId,
            data: createData,
          });
        }
        handleClosePropertyModal();
      } catch (err) {
        setPropertyErrors({
          name: err instanceof Error ? err.message : 'Failed to save property',
        });
      }
    },
    [
      propertyForm,
      editingProperty,
      householdId,
      validatePropertyForm,
      createProperty,
      updateProperty,
      handleClosePropertyModal,
    ]
  );

  const handleOpenDeletePropertyModal = useCallback((property: PropertyResponse) => {
    setDeletingProperty(property);
    setIsDeletePropertyModalOpen(true);
  }, []);

  const handleCloseDeletePropertyModal = useCallback(() => {
    setIsDeletePropertyModalOpen(false);
    setDeletingProperty(null);
  }, []);

  const handleDeleteProperty = useCallback(async () => {
    if (!deletingProperty) return;

    try {
      await deleteProperty.mutateAsync({
        propertyId: deletingProperty.id,
        householdId,
      });
      handleCloseDeletePropertyModal();
    } catch {
      // Error will be shown by mutation state
    }
  }, [deletingProperty, householdId, deleteProperty, handleCloseDeletePropertyModal]);

  // =============================================================================
  // Area Handlers
  // =============================================================================

  const handleOpenAddAreaModal = useCallback((propertyId: number) => {
    setEditingArea(null);
    setAreaPropertyId(propertyId);
    setAreaForm(DEFAULT_AREA_FORM);
    setAreaErrors({});
    setIsAreaModalOpen(true);
  }, []);

  const handleOpenEditAreaModal = useCallback((area: AreaResponse) => {
    setEditingArea(area);
    setAreaPropertyId(area.property_id);
    setAreaForm({
      name: area.name,
      description: area.description ?? '',
      color: area.color,
    });
    setAreaErrors({});
    setIsAreaModalOpen(true);
  }, []);

  const handleCloseAreaModal = useCallback(() => {
    setIsAreaModalOpen(false);
    setEditingArea(null);
    setAreaPropertyId(null);
    setAreaForm(DEFAULT_AREA_FORM);
    setAreaErrors({});
  }, []);

  const validateAreaForm = useCallback((data: AreaFormData): AreaFormErrors => {
    const errors: AreaFormErrors = {};
    if (!data.name.trim()) {
      errors.name = 'Area name is required';
    } else if (data.name.length > 100) {
      errors.name = 'Area name must be 100 characters or less';
    }
    if (data.description && data.description.length > 1000) {
      errors.description = 'Description must be 1000 characters or less';
    }
    if (!data.color.match(/^#[0-9A-Fa-f]{6}$/)) {
      errors.color = 'Invalid color format';
    }
    return errors;
  }, []);

  const handleSubmitArea = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      const errors = validateAreaForm(areaForm);
      if (Object.keys(errors).length > 0) {
        setAreaErrors(errors);
        return;
      }

      setAreaErrors({});

      try {
        if (editingArea) {
          const updateData: AreaUpdate = {
            name: areaForm.name.trim(),
            description: areaForm.description.trim() || undefined,
            color: areaForm.color.toUpperCase(),
          };
          await updateArea.mutateAsync({
            areaId: editingArea.id,
            data: updateData,
          });
        } else if (areaPropertyId) {
          const createData: AreaCreate = {
            name: areaForm.name.trim(),
            description: areaForm.description.trim() || undefined,
            color: areaForm.color.toUpperCase(),
          };
          await createArea.mutateAsync({
            propertyId: areaPropertyId,
            data: createData,
          });
        }
        handleCloseAreaModal();
      } catch (err) {
        setAreaErrors({
          name: err instanceof Error ? err.message : 'Failed to save area',
        });
      }
    },
    [
      areaForm,
      editingArea,
      areaPropertyId,
      validateAreaForm,
      createArea,
      updateArea,
      handleCloseAreaModal,
    ]
  );

  const handleOpenDeleteAreaModal = useCallback((area: AreaResponse) => {
    setDeletingArea(area);
    setIsDeleteAreaModalOpen(true);
  }, []);

  const handleCloseDeleteAreaModal = useCallback(() => {
    setIsDeleteAreaModalOpen(false);
    setDeletingArea(null);
  }, []);

  const handleDeleteArea = useCallback(async () => {
    if (!deletingArea) return;

    try {
      await deleteArea.mutateAsync({
        areaId: deletingArea.id,
        propertyId: deletingArea.property_id,
      });
      handleCloseDeleteAreaModal();
    } catch {
      // Error will be shown by mutation state
    }
  }, [deletingArea, deleteArea, handleCloseDeleteAreaModal]);

  // =============================================================================
  // Render
  // =============================================================================

  const isSubmittingProperty = createProperty.isPending || updateProperty.isPending;
  const isSubmittingArea = createArea.isPending || updateArea.isPending;
  const isDeletingProperty = deleteProperty.isPending;
  const isDeletingArea = deleteArea.isPending;

  if (isLoading) {
    return (
      <div className={clsx('flex items-center justify-center py-12', className)}>
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-primary" />
        <span className="text-text-secondary">Loading properties...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        title="Error loading properties"
        message={error}
        onRetry={() => void refetch()}
        className={className}
        testId="property-management-error"
      />
    );
  }

  return (
    <div className={clsx('space-y-6', className)} data-testid="property-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Properties</h2>
          <p className="mt-1 text-sm text-text-secondary">Manage your properties and their areas</p>
        </div>
        <button
          onClick={handleOpenAddPropertyModal}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
          data-testid="add-property-btn"
        >
          <Plus className="h-4 w-4" />
          Add Property
        </button>
      </div>

      {/* Properties List */}
      {properties.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-card p-8 text-center">
          <Building2 className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-text-primary">No properties configured</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Add your first property to organize your cameras by location.
          </p>
          <button
            onClick={handleOpenAddPropertyModal}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="add-property-empty-btn"
          >
            <Plus className="h-4 w-4" />
            Add Property
          </button>
        </div>
      ) : (
        <div className="space-y-3" data-testid="properties-list">
          {properties.map((property) => (
            <PropertyAccordion
              key={property.id}
              property={property}
              isExpanded={expandedProperties.has(property.id)}
              onToggle={() => toggleProperty(property.id)}
              onEdit={() => handleOpenEditPropertyModal(property)}
              onDelete={() => handleOpenDeletePropertyModal(property)}
              onEditArea={handleOpenEditAreaModal}
              onDeleteArea={handleOpenDeleteAreaModal}
              onAddArea={() => handleOpenAddAreaModal(property.id)}
            />
          ))}
        </div>
      )}

      {/* Add/Edit Property Modal */}
      <Transition appear show={isPropertyModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleClosePropertyModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      {editingProperty ? 'Edit Property' : 'Add Property'}
                    </Dialog.Title>
                    <button
                      onClick={handleClosePropertyModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <form onSubmit={(e) => void handleSubmitProperty(e)} className="mt-6 space-y-4">
                    {/* Name Input */}
                    <div>
                      <label
                        htmlFor="property-name"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Property Name
                      </label>
                      <input
                        type="text"
                        id="property-name"
                        data-testid="property-name-input"
                        value={propertyForm.name}
                        onChange={(e) => setPropertyForm({ ...propertyForm, name: e.target.value })}
                        maxLength={100}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          propertyErrors.name
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="Main House"
                      />
                      {propertyErrors.name && (
                        <p className="mt-1 text-sm text-red-500">{propertyErrors.name}</p>
                      )}
                    </div>

                    {/* Address Input */}
                    <div>
                      <label
                        htmlFor="property-address"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Address (optional)
                      </label>
                      <input
                        type="text"
                        id="property-address"
                        data-testid="property-address-input"
                        value={propertyForm.address}
                        onChange={(e) =>
                          setPropertyForm({ ...propertyForm, address: e.target.value })
                        }
                        maxLength={500}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          propertyErrors.address
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="123 Main St, City, ST 12345"
                      />
                      {propertyErrors.address && (
                        <p className="mt-1 text-sm text-red-500">{propertyErrors.address}</p>
                      )}
                    </div>

                    {/* Timezone Select */}
                    <div>
                      <label
                        htmlFor="property-timezone"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Timezone
                      </label>
                      <select
                        id="property-timezone"
                        data-testid="property-timezone-select"
                        value={propertyForm.timezone}
                        onChange={(e) =>
                          setPropertyForm({ ...propertyForm, timezone: e.target.value })
                        }
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          propertyErrors.timezone
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                      >
                        {COMMON_TIMEZONES.map((tz) => (
                          <option key={tz} value={tz}>
                            {tz}
                          </option>
                        ))}
                      </select>
                      {propertyErrors.timezone && (
                        <p className="mt-1 text-sm text-red-500">{propertyErrors.timezone}</p>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end gap-3 pt-4">
                      <button
                        type="button"
                        onClick={handleClosePropertyModal}
                        disabled={isSubmittingProperty}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isSubmittingProperty}
                        data-testid="save-property-btn"
                        className="inline-flex items-center rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                      >
                        {isSubmittingProperty && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {editingProperty ? 'Update' : 'Add Property'}
                      </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Add/Edit Area Modal */}
      <Transition appear show={isAreaModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseAreaModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      {editingArea ? 'Edit Area' : 'Add Area'}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseAreaModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <form onSubmit={(e) => void handleSubmitArea(e)} className="mt-6 space-y-4">
                    {/* Name Input */}
                    <div>
                      <label
                        htmlFor="area-name"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Area Name
                      </label>
                      <input
                        type="text"
                        id="area-name"
                        data-testid="area-name-input"
                        value={areaForm.name}
                        onChange={(e) => setAreaForm({ ...areaForm, name: e.target.value })}
                        maxLength={100}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          areaErrors.name
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="Front Yard"
                      />
                      {areaErrors.name && (
                        <p className="mt-1 text-sm text-red-500">{areaErrors.name}</p>
                      )}
                    </div>

                    {/* Description Input */}
                    <div>
                      <label
                        htmlFor="area-description"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Description (optional)
                      </label>
                      <textarea
                        id="area-description"
                        data-testid="area-description-input"
                        value={areaForm.description}
                        onChange={(e) => setAreaForm({ ...areaForm, description: e.target.value })}
                        maxLength={1000}
                        rows={3}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          areaErrors.description
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="Main entrance and lawn area"
                      />
                      {areaErrors.description && (
                        <p className="mt-1 text-sm text-red-500">{areaErrors.description}</p>
                      )}
                    </div>

                    {/* Color Select */}
                    <div>
                      <label
                        htmlFor="area-color"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Color
                      </label>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {AREA_COLORS.map((color) => (
                          <button
                            key={color.value}
                            type="button"
                            onClick={() => setAreaForm({ ...areaForm, color: color.value })}
                            className={clsx(
                              'h-8 w-8 rounded-full border-2 transition-transform hover:scale-110',
                              areaForm.color.toUpperCase() === color.value.toUpperCase()
                                ? 'border-white ring-2 ring-white/50'
                                : 'border-transparent'
                            )}
                            style={{ backgroundColor: color.value }}
                            aria-label={color.label}
                            title={color.label}
                            data-testid={`area-color-${color.value.replace('#', '')}`}
                          />
                        ))}
                      </div>
                      {areaErrors.color && (
                        <p className="mt-1 text-sm text-red-500">{areaErrors.color}</p>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end gap-3 pt-4">
                      <button
                        type="button"
                        onClick={handleCloseAreaModal}
                        disabled={isSubmittingArea}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isSubmittingArea}
                        data-testid="save-area-btn"
                        className="inline-flex items-center rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                      >
                        {isSubmittingArea && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {editingArea ? 'Update' : 'Add Area'}
                      </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Property Confirmation Modal */}
      <Transition appear show={isDeletePropertyModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseDeletePropertyModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                      <AlertCircle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <Dialog.Title className="text-lg font-semibold text-text-primary">
                        Delete Property
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-text-secondary">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-text-primary">
                          {deletingProperty?.name}
                        </span>
                        ? This will also delete all areas within this property. This action cannot
                        be undone.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeletePropertyModal}
                      disabled={isDeletingProperty}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteProperty()}
                      disabled={isDeletingProperty}
                      data-testid="confirm-delete-property-btn"
                      className="inline-flex items-center rounded-lg bg-red-700 px-4 py-2 font-medium text-white transition-all hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 disabled:opacity-50"
                    >
                      {isDeletingProperty && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Delete Property
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Area Confirmation Modal */}
      <Transition appear show={isDeleteAreaModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseDeleteAreaModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                      <AlertCircle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <Dialog.Title className="text-lg font-semibold text-text-primary">
                        Delete Area
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-text-secondary">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-text-primary">{deletingArea?.name}</span>?
                        Cameras linked to this area will be unlinked but not deleted. This action
                        cannot be undone.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeleteAreaModal}
                      disabled={isDeletingArea}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteArea()}
                      disabled={isDeletingArea}
                      data-testid="confirm-delete-area-btn"
                      className="inline-flex items-center rounded-lg bg-red-700 px-4 py-2 font-medium text-white transition-all hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 disabled:opacity-50"
                    >
                      {isDeletingArea && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Delete Area
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
