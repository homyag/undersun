import { createApp, type Component } from 'vue';
import PrimeVue from 'primevue/config';
import MatchingApp from './MatchingApp.vue';
import MatchingSelectApp from './MatchingSelectApp.vue';
import OverviewApp from './OverviewApp.vue';
import MediaPreviewApp from './MediaPreviewApp.vue';
import MediaJobApp from './MediaJobApp.vue';
import BulkMediaPreviewApp from './BulkMediaPreviewApp.vue';
import QueuedMediaApp from './QueuedMediaApp.vue';
import ReviewQueueApp from './ReviewQueueApp.vue';
import PriceReviewApp from './PriceReviewApp.vue';
import PriceReviewListApp from './PriceReviewListApp.vue';
import UnlinkedApp from './UnlinkedApp.vue';
import AssetListApp from './AssetListApp.vue';
import AssetDetailApp from './AssetDetailApp.vue';
import GroupListApp from './GroupListApp.vue';
import GroupDetailApp from './GroupDetailApp.vue';
import SyncRunListApp from './SyncRunListApp.vue';
import SyncRunDetailApp from './SyncRunDetailApp.vue';
import LocationMappingListApp from './LocationMappingListApp.vue';
import LocationMappingDetailApp from './LocationMappingDetailApp.vue';
import PropertyChangeListApp from './PropertyChangeListApp.vue';
import PropertyChangeDetailApp from './PropertyChangeDetailApp.vue';
import UnitListApp from './UnitListApp.vue';
import UnitDetailApp from './UnitDetailApp.vue';
import SkippedUnitListApp from './SkippedUnitListApp.vue';
import SkippedUnitDetailApp from './SkippedUnitDetailApp.vue';
import PaymentPlanListApp from './PaymentPlanListApp.vue';
import PaymentPlanDetailApp from './PaymentPlanDetailApp.vue';
import SyncEventListApp from './SyncEventListApp.vue';
import SyncEventDetailApp from './SyncEventDetailApp.vue';
import SyncStateListApp from './SyncStateListApp.vue';
import SyncStateDetailApp from './SyncStateDetailApp.vue';
import PropertyAssetListApp from './PropertyAssetListApp.vue';
import PropertyAssetDetailApp from './PropertyAssetDetailApp.vue';
import ProjectDetailApp from './ProjectDetailApp.vue';
import ReadinessApp from './ReadinessApp.vue';
import GroupCreateApp from './GroupCreateApp.vue';
import DetachPropertyApp from './DetachPropertyApp.vue';
import { undersunPreset } from './theme';
import './style.css';
import type { MatchingData } from './model';

function mount<T extends Record<string, unknown>>(component: Component, props: T, root: HTMLElement) {
  createApp(component, props).use(PrimeVue, {
    theme: { preset: undersunPreset, options: { darkModeSelector: 'none' } },
  }).mount(root);
}

const root = document.getElementById('arealisting-vue-root');
const bootstrap = document.getElementById('matching-data');
if (root && bootstrap?.textContent) {
  mount(MatchingApp, {
    data: JSON.parse(bootstrap.textContent) as MatchingData,
    unlinkedUrl: root.dataset.unlinkedUrl || '',
    projectsUrl: root.dataset.projectsUrl || '',
  }, root);
}

const matchingSelectRoot = document.getElementById('arealisting-matching-select-root');
const matchingSelectData = document.getElementById('matching-select-data');
if (matchingSelectRoot && matchingSelectData?.textContent) {
  mount(MatchingSelectApp, { data: JSON.parse(matchingSelectData.textContent) }, matchingSelectRoot);
}

const overviewRoot = document.getElementById('arealisting-overview-root');
const totals = document.getElementById('arealisting-overview-totals');
const attention = document.getElementById('arealisting-overview-actionable');
if (overviewRoot && totals?.textContent && attention?.textContent) {
  mount(OverviewApp, {
    totals: JSON.parse(totals.textContent),
    attentionCount: JSON.parse(attention.textContent),
  }, overviewRoot);
}

const mediaRoot = document.getElementById('arealisting-media-preview-root');
const mediaData = document.getElementById('media-preview-data');
if (mediaRoot && mediaData?.textContent) {
  mount(MediaPreviewApp, { data: JSON.parse(mediaData.textContent) }, mediaRoot);
}

const mediaJobRoot = document.getElementById('arealisting-media-job-root');
const mediaJobData = document.getElementById('media-job-data');
if (mediaJobRoot && mediaJobData?.textContent) {
  mount(MediaJobApp, { data: JSON.parse(mediaJobData.textContent) }, mediaJobRoot);
}

const bulkMediaRoot = document.getElementById('arealisting-bulk-media-root');
const bulkMediaData = document.getElementById('bulk-media-preview-data');
if (bulkMediaRoot && bulkMediaData?.textContent) {
  mount(BulkMediaPreviewApp, { data: JSON.parse(bulkMediaData.textContent) }, bulkMediaRoot);
}

const queuedMediaRoot = document.getElementById('arealisting-queued-media-root');
const queuedMediaData = document.getElementById('queued-media-data');
if (queuedMediaRoot && queuedMediaData?.textContent) {
  mount(QueuedMediaApp, { data: JSON.parse(queuedMediaData.textContent) }, queuedMediaRoot);
}

const reviewQueueRoot = document.getElementById('arealisting-review-queue-root');
const reviewQueueData = document.getElementById('review-queue-data');
if (reviewQueueRoot && reviewQueueData?.textContent) {
  mount(ReviewQueueApp, { data: JSON.parse(reviewQueueData.textContent) }, reviewQueueRoot);
}

const priceReviewRoot = document.getElementById('arealisting-price-review-root');
const priceReviewData = document.getElementById('price-review-data');
if (priceReviewRoot && priceReviewData?.textContent) {
  mount(PriceReviewApp, { data: JSON.parse(priceReviewData.textContent) }, priceReviewRoot);
}

const priceReviewListRoot = document.getElementById('arealisting-price-review-list-root');
const priceReviewListData = document.getElementById('price-review-list-data');
if (priceReviewListRoot && priceReviewListData?.textContent) {
  mount(PriceReviewListApp, { data: JSON.parse(priceReviewListData.textContent) }, priceReviewListRoot);
}

const unlinkedRoot = document.getElementById('arealisting-unlinked-root');
const unlinkedData = document.getElementById('unlinked-data');
if (unlinkedRoot && unlinkedData?.textContent) {
  mount(UnlinkedApp, { data: JSON.parse(unlinkedData.textContent) }, unlinkedRoot);
}

const assetListRoot = document.getElementById('arealisting-asset-list-root');
const assetListData = document.getElementById('asset-list-data');
if (assetListRoot && assetListData?.textContent) {
  mount(AssetListApp, { data: JSON.parse(assetListData.textContent) }, assetListRoot);
}

const assetDetailRoot = document.getElementById('arealisting-asset-detail-root');
const assetDetailData = document.getElementById('asset-detail-data');
if (assetDetailRoot && assetDetailData?.textContent) {
  mount(AssetDetailApp, { data: JSON.parse(assetDetailData.textContent) }, assetDetailRoot);
}

const groupListRoot = document.getElementById('arealisting-group-list-root');
const groupListData = document.getElementById('group-list-data');
if (groupListRoot && groupListData?.textContent) {
  mount(GroupListApp, { data: JSON.parse(groupListData.textContent) }, groupListRoot);
}

const groupDetailRoot = document.getElementById('arealisting-group-detail-root');
const groupDetailData = document.getElementById('group-detail-data');
if (groupDetailRoot && groupDetailData?.textContent) {
  mount(GroupDetailApp, { data: JSON.parse(groupDetailData.textContent) }, groupDetailRoot);
}

const syncRunListRoot = document.getElementById('arealisting-sync-run-list-root');
const syncRunListData = document.getElementById('sync-run-list-data');
if (syncRunListRoot && syncRunListData?.textContent) {
  mount(SyncRunListApp, { data: JSON.parse(syncRunListData.textContent) }, syncRunListRoot);
}

const syncRunDetailRoot = document.getElementById('arealisting-sync-run-detail-root');
const syncRunDetailData = document.getElementById('sync-run-detail-data');
if (syncRunDetailRoot && syncRunDetailData?.textContent) {
  mount(SyncRunDetailApp, { data: JSON.parse(syncRunDetailData.textContent) }, syncRunDetailRoot);
}

const locationMappingListRoot = document.getElementById('arealisting-location-mapping-list-root');
const locationMappingListData = document.getElementById('location-mapping-list-data');
if (locationMappingListRoot && locationMappingListData?.textContent) {
  mount(LocationMappingListApp, { data: JSON.parse(locationMappingListData.textContent) }, locationMappingListRoot);
}

const locationMappingDetailRoot = document.getElementById('arealisting-location-mapping-detail-root');
const locationMappingDetailData = document.getElementById('location-mapping-detail-data');
if (locationMappingDetailRoot && locationMappingDetailData?.textContent) {
  mount(LocationMappingDetailApp, { data: JSON.parse(locationMappingDetailData.textContent) }, locationMappingDetailRoot);
}

const propertyChangeListRoot = document.getElementById('arealisting-property-change-list-root');
const propertyChangeListData = document.getElementById('property-change-list-data');
if (propertyChangeListRoot && propertyChangeListData?.textContent) {
  mount(PropertyChangeListApp, { data: JSON.parse(propertyChangeListData.textContent) }, propertyChangeListRoot);
}

const propertyChangeDetailRoot = document.getElementById('arealisting-property-change-detail-root');
const propertyChangeDetailData = document.getElementById('property-change-detail-data');
if (propertyChangeDetailRoot && propertyChangeDetailData?.textContent) {
  mount(PropertyChangeDetailApp, { data: JSON.parse(propertyChangeDetailData.textContent) }, propertyChangeDetailRoot);
}

const unitListRoot = document.getElementById('arealisting-unit-list-root');
const unitListData = document.getElementById('unit-list-data');
if (unitListRoot && unitListData?.textContent) {
  mount(UnitListApp, { data: JSON.parse(unitListData.textContent) }, unitListRoot);
}

const unitDetailRoot = document.getElementById('arealisting-unit-detail-root');
const unitDetailData = document.getElementById('unit-detail-data');
if (unitDetailRoot && unitDetailData?.textContent) {
  mount(UnitDetailApp, { data: JSON.parse(unitDetailData.textContent) }, unitDetailRoot);
}

const skippedUnitListRoot = document.getElementById('arealisting-skipped-unit-list-root');
const skippedUnitListData = document.getElementById('skipped-unit-list-data');
if (skippedUnitListRoot && skippedUnitListData?.textContent) {
  mount(SkippedUnitListApp, { data: JSON.parse(skippedUnitListData.textContent) }, skippedUnitListRoot);
}

const skippedUnitDetailRoot = document.getElementById('arealisting-skipped-unit-detail-root');
const skippedUnitDetailData = document.getElementById('skipped-unit-detail-data');
if (skippedUnitDetailRoot && skippedUnitDetailData?.textContent) {
  mount(SkippedUnitDetailApp, { data: JSON.parse(skippedUnitDetailData.textContent) }, skippedUnitDetailRoot);
}

const paymentPlanListRoot = document.getElementById('arealisting-payment-plan-list-root');
const paymentPlanListData = document.getElementById('payment-plan-list-data');
if (paymentPlanListRoot && paymentPlanListData?.textContent) {
  mount(PaymentPlanListApp, { data: JSON.parse(paymentPlanListData.textContent) }, paymentPlanListRoot);
}

const paymentPlanDetailRoot = document.getElementById('arealisting-payment-plan-detail-root');
const paymentPlanDetailData = document.getElementById('payment-plan-detail-data');
if (paymentPlanDetailRoot && paymentPlanDetailData?.textContent) {
  mount(PaymentPlanDetailApp, { data: JSON.parse(paymentPlanDetailData.textContent) }, paymentPlanDetailRoot);
}

const syncEventListRoot = document.getElementById('arealisting-sync-event-list-root');
const syncEventListData = document.getElementById('sync-event-list-data');
if (syncEventListRoot && syncEventListData?.textContent) {
  mount(SyncEventListApp, { data: JSON.parse(syncEventListData.textContent) }, syncEventListRoot);
}

const syncEventDetailRoot = document.getElementById('arealisting-sync-event-detail-root');
const syncEventDetailData = document.getElementById('sync-event-detail-data');
if (syncEventDetailRoot && syncEventDetailData?.textContent) {
  mount(SyncEventDetailApp, { data: JSON.parse(syncEventDetailData.textContent) }, syncEventDetailRoot);
}

const syncStateListRoot = document.getElementById('arealisting-sync-state-list-root');
const syncStateListData = document.getElementById('sync-state-list-data');
if (syncStateListRoot && syncStateListData?.textContent) {
  mount(SyncStateListApp, { data: JSON.parse(syncStateListData.textContent) }, syncStateListRoot);
}

const syncStateDetailRoot = document.getElementById('arealisting-sync-state-detail-root');
const syncStateDetailData = document.getElementById('sync-state-detail-data');
if (syncStateDetailRoot && syncStateDetailData?.textContent) {
  mount(SyncStateDetailApp, { data: JSON.parse(syncStateDetailData.textContent) }, syncStateDetailRoot);
}

const propertyAssetListRoot = document.getElementById('arealisting-property-asset-list-root');
const propertyAssetListData = document.getElementById('property-asset-list-data');
if (propertyAssetListRoot && propertyAssetListData?.textContent) {
  mount(PropertyAssetListApp, { data: JSON.parse(propertyAssetListData.textContent) }, propertyAssetListRoot);
}

const propertyAssetDetailRoot = document.getElementById('arealisting-property-asset-detail-root');
const propertyAssetDetailData = document.getElementById('property-asset-detail-data');
if (propertyAssetDetailRoot && propertyAssetDetailData?.textContent) {
  mount(PropertyAssetDetailApp, { data: JSON.parse(propertyAssetDetailData.textContent) }, propertyAssetDetailRoot);
}

const projectDetailRoot = document.getElementById('arealisting-project-detail-root');
const projectDetailData = document.getElementById('project-detail-data');
if (projectDetailRoot && projectDetailData?.textContent) {
  mount(ProjectDetailApp, { data: JSON.parse(projectDetailData.textContent) }, projectDetailRoot);
}

const readinessRoot = document.getElementById('arealisting-readiness-root');
const readinessData = document.getElementById('readiness-data');
if (readinessRoot && readinessData?.textContent) {
  mount(ReadinessApp, { data: JSON.parse(readinessData.textContent) }, readinessRoot);
}

const groupCreateRoot = document.getElementById('arealisting-group-create-root');
const groupCreateData = document.getElementById('group-create-data');
if (groupCreateRoot && groupCreateData?.textContent) {
  mount(GroupCreateApp, { data: JSON.parse(groupCreateData.textContent) }, groupCreateRoot);
}

const detachPropertyRoot = document.getElementById('arealisting-detach-property-root');
const detachPropertyData = document.getElementById('detach-property-data');
if (detachPropertyRoot && detachPropertyData?.textContent) {
  mount(DetachPropertyApp, { data: JSON.parse(detachPropertyData.textContent) }, detachPropertyRoot);
}
