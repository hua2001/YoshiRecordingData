# -*- coding: utf-8 -*-
"""
Created on Sat Dec 26 22:27:13 2015

@author: Administrator
"""

import pickle
import itertools

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import pearsonr

from simulation import (
    SimFiber, fill_between_curves, fill_between_geom_curves,
    control_list, quantity_list,
    MAX_RADIUS, MAX_TIME, MAX_RATE_TIME, FIBER_MECH_ID,
    STATIC_END, STATIC_START, DT)


fs = 1 / DT
stim_num = 7
level_num = 6
level_plot_iter = range(6)
stim_plot_list = [3, 4, 5]
quantity_plot_list = ['strain', 'sener', 'stress']
stim_neural_quant_iter = range(2, stim_num)
representative_stim_num = 5
transform_list = [(0, 'strain'), (0, 'sener'), (1, 'stress')]
transform_list_full = list(itertools.product((0, 1),
                                             ('strain', 'sener', 'stress')))


def get_color(stim):
    color = np.zeros(3, dtype='i')
    color[stim_plot_list.index(stim)] = 1
    color = tuple(color)
    return color


class RepSample(SimFiber):

    def __init__(self, sample_id, control, stim_num):
        self.factor = 'RepSample'
        self.level = sample_id
        self.control = control
        self.stim_num = stim_num
        self.fs = 1 / DT
        self.get_dist()
        self.load_traces()
        self.load_trans_params()
        self.get_predicted_fr()
        self.get_dist_fr()
        self.get_mi()
        self.get_line_fit()


def plot_variance(repSample_list):
    fig, axs = plt.subplots(3, 1, figsize=(3.5, 6))
    for stim in stim_plot_list:
        color = get_color(stim)
        displ_time_array_list = []
        displ_strain_array_list = []
        displ_sener_array_list = []
        force_time_array_list = []
        force_stress_array_list = []
        for level in range(5):
            repSampleDispl = repSample_list[level][0]
            repSampleForce = repSample_list[level][1]
            displ_time_array_list.append(
                repSampleDispl.traces[stim]['time'][::100])
            displ_strain_array_list.append(
                repSampleDispl.traces[stim]['strain'][::100])
            displ_sener_array_list.append(
                repSampleDispl.traces[stim]['sener'][::100] / 1e3)
            force_time_array_list.append(
                repSampleForce.traces[stim]['time'][::100])
            force_stress_array_list.append(
                repSampleForce.traces[stim]['stress'][::100] / 1e3)
        kwargs = dict(alpha=.25, fc=color, ec='none', label=stim)
        fill_between_curves(displ_time_array_list, displ_strain_array_list,
                            axs[0], **kwargs)
        fill_between_curves(displ_time_array_list, displ_sener_array_list,
                            axs[1], **kwargs)
        fill_between_curves(force_time_array_list, force_stress_array_list,
                            axs[2], **kwargs)
        axs[0].plot(repSample_list[0][0].traces[stim]['time'],
                    repSample_list[0][0].traces[stim]['strain'],
                    '-', color=color, label='Average skin')
        axs[1].plot(repSample_list[0][0].traces[stim]['time'],
                    repSample_list[0][0].traces[stim][
                        'sener'] / 1e3,
                    '-', color=color, label='Average skin')
        axs[2].plot(repSample_list[0][1].traces[stim]['time'],
                    repSample_list[0][1].traces[stim][
                        'stress'] / 1e3,
                    '-', color=color, label='Average skin')
        # Plot the bars

        def get_min_max(array_list):
            arr_end_arr = np.array([array[-1] for array in array_list])
            return (arr_end_arr.min(), arr_end_arr.max())
        for i, array_list in enumerate([displ_strain_array_list,
                                        displ_sener_array_list,
                                        force_stress_array_list]):
            axes = axs[i]
            axes.plot([MAX_TIME + .1 + .1 * (stim - stim_plot_list[0])] * 2,
                      get_min_max(array_list),
                      lw=2.5, color=color, alpha=.5, clip_on=False)
    # Set x and y lim
    for axes in axs.ravel():
        axes.set_xlim(0, MAX_TIME)
    # Formatting labels
    # x-axis
    axs[-1].set_xlabel('Time (s)')
    # y-axis for the Stimulus magnitude over time
    axs[0].set_ylabel('Interior strain')
    axs[0].set_title('Controlled surface deflection')
    axs[1].set_ylabel(r'Interior SED (kPa/$m^3$)')
    axs[1].set_title('Controlled surface deflection')
    axs[2].set_ylabel('Interior stress (kPa)')
    axs[2].set_title('Controlled surface pressure')
    # Added panel labels
    for axes_id, axes in enumerate(axs.ravel()):
        axes.text(-.2, 1.05, chr(65+axes_id), transform=axes.transAxes,
                  fontsize=12, fontweight='bold', va='top')
    # Save figure
    fig.tight_layout()
    fig.subplots_adjust(right=.95)
    fig.savefig('./plots/RepSample/variance.png', dpi=300)
    fig.savefig('./plots/RepSample/variance.pdf', dpi=300)
    plt.close(fig)


def quantify_variance(repSample_list):

    def get_inter_skin(control, quantity, stim):
        quantity_arr = np.array([
            repSample_list[level][control].traces[stim][quantity][-1]
            for level in range(level_num)])
        return quantity_arr.max() - quantity_arr.min()

    def get_inter_stimulus(control, quantity, level):
        quantity_arr = np.array([
            repSample_list[level][control].traces[stim][quantity][-1]
            for stim in range(stim_num)])
        return np.diff(quantity_arr[stim_plot_list]).mean()

    def get_isrd(control, quantity):
        inter_skin = get_inter_skin(control, quantity, stim_plot_list[1])
        inter_stimulus = get_inter_stimulus(control, quantity, 0)
        return inter_skin / inter_stimulus

    isrd_list = []
    for control, quantity in transform_list:
        isrd_list.append(get_isrd(control, quantity))
    return isrd_list


def fine_interp_array(dist, quantity, loc_index):
    time = dist['time'][:, 0]
    time_fine = np.arange(0, time.max(), DT)
    array = dist[quantity][:, loc_index]
    array_fine = np.interp(time_fine, time, array)
    return time_fine, array_fine


def get_dist_static_mean(dist, quantity):
    # Get max_index amd max_loc_index
    if quantity.startswith('m'):
        time_fine, stress_fine = fine_interp_array(dist, 'mstress', 0)
        max_index = stress_fine.argmax()
        max_loc_index = dist['mstress'].shape[1]
    elif quantity.startswith('c'):
        time_fine, press_fine = fine_interp_array(dist, 'cpress', 0)
        max_index = press_fine.argmax()
        max_loc_index = dist['cpress'].shape[1]
    static_mean_array = np.empty(max_loc_index)
    for loc_index in range(max_loc_index):
        time_fine, array_fine = fine_interp_array(dist, quantity, loc_index)
        static_start_index = max_index + int(fs * STATIC_START)
        static_end_index = max_index + int(fs * STATIC_END)
        static_mean_array[loc_index] = array_fine[
            static_start_index:static_end_index].mean()
    return static_mean_array


def plot_shape(repSample_list, with_color=True):
    fig_rate, axs_rate = plt.subplots(3, 1, figsize=(3.5, 6))
    fig_geom, axs_geom = plt.subplots(3, 1, figsize=(3.5, 6))
    stim = representative_stim_num
    level = 0
    color = get_color(stim) if with_color else 'k'
    repSampleDispl = repSample_list[level][0]
    repSampleForce = repSample_list[level][1]
    axs_rate[0].plot(repSampleDispl.traces_rate[stim]['time'],
                     repSampleDispl.traces_rate[stim]['strain'],
                     '-', c=color, label='Interior strain rate')
    axs_rate_0_twin = axs_rate[0].twinx()
    axs_rate_0_twin.plot(repSampleDispl.traces_rate[stim]['time'],
                         repSampleDispl.traces_rate[stim]['displ'] * 1e3,
                         '--', c=color, label='Surface velocity')
    axs_rate[1].plot(repSampleForce.traces_rate[stim]['time'],
                     repSampleForce.traces_rate[stim]['sener'] * 1e-3,
                     '-', c=color, label=r'Interior SED rate')
    axs_rate_1_twin = axs_rate[1].twinx()
    axs_rate_1_twin.plot(repSampleDispl.traces_rate[stim]['time'],
                         repSampleDispl.traces_rate[stim]['displ'] * 1e3,
                         '--', c=color, label='Surface velocity')
    axs_rate[2].plot(repSampleForce.traces_rate[stim]['time'],
                     repSampleForce.traces_rate[stim]['stress'] * 1e-3,
                     '-', c=color, label='Interior stress rate')
    axs_rate_2_twin = axs_rate[2].twinx()
    axs_rate_2_twin.plot(repSampleForce.traces_rate[stim]['time'],
                         repSampleForce.traces_rate[stim]['press'] * 1e-3,
                         '--', c=color, label='Surface pressure')
    dist_displ = repSampleDispl.dist[stim]
    dist_force = repSampleForce.dist[stim]
    axs_geom[0].plot(dist_displ['mxold'][-1, :] * 1e3,
                     get_dist_static_mean(dist_displ, 'mstrain'),
                     '-', c=color, label='Interior strain')
    axs_geom_0_twin = axs_geom[0].twinx()
    axs_geom_0_twin.plot(dist_displ['cxold'][-1, :] * 1e3,
                         get_dist_static_mean(dist_displ, 'cy') * 1e-3,
                         '--', c=color, label='Surface deflection')
    axs_geom[1].plot(dist_displ['mxold'][-1, :] * 1e3,
                     get_dist_static_mean(dist_displ, 'msener') * 1e-3,
                     '-', c=color, label='Interior SED')
    axs_geom_1_twin = axs_geom[1].twinx()
    axs_geom_1_twin.plot(dist_displ['cxold'][-1, :] * 1e3,
                         get_dist_static_mean(dist_displ, 'cy') * 1e-3,
                         '--', c=color, label='Surface deflection')
    axs_geom[2].plot(dist_force['mxold'][-1, :] * 1e3,
                     get_dist_static_mean(dist_force, 'mstress') * 1e-3,
                     '-', c=color, label='Interior stress')
    axs_geom_2_twin = axs_geom[2].twinx()
    axs_geom_2_twin.plot(dist_force['cxold'][-1, :] * 1e3,
                         get_dist_static_mean(dist_force, 'cpress') * 1e-3,
                         '--', c=color, label='Surface pressure')
    # Set x and y lim
    for axes in axs_rate.ravel():
        axes.set_xlim(0, MAX_RATE_TIME)
    for axes in axs_geom.ravel():
        axes.set_xlim(0, MAX_RADIUS * 1e3)
    # Formatting labels
    # x-axis
    axs_rate[-1].set_xlabel('Time (s)')
    axs_geom[-1].set_xlabel('Location (mm)')
    # y-axis
    axs_rate[0].set_ylabel(r'Interior strain rate (s$^{-1}$)')
    axs_rate[0].set_title('Controlled surface deflection')
    axs_rate_0_twin.set_ylabel(r'Surface velocity (mm/s)')
    axs_rate[1].set_ylabel(r'Interior SED rate (kPa$\cdot m^3$/s)')
    axs_rate[1].set_title('Controlled surface deflection')
    axs_rate_1_twin.set_ylabel(r'Surface velocity (mm/s)')
    axs_rate[2].set_ylabel('Interior stress rate (kPa/s)')
    axs_rate[2].set_title('Controlled surface pressure')
    axs_rate_2_twin.set_ylabel(r'Surface pressure rate (kPa/s)')
    axs_geom[0].set_ylabel('Interior strain')
    axs_geom[0].set_title('Controlled surface deflection')
    axs_geom_0_twin.set_ylabel(r'Surface deflection (mm)')
    axs_geom[1].set_ylabel('Interior SED (kJ/$m^3$)')
    axs_geom[1].set_title('Controlled surface deflection')
    axs_geom_1_twin.set_ylabel(r'Surface deflection (mm)')
    axs_geom[2].set_ylabel('Interior stress (kPa)')
    axs_geom[2].set_title('Controlled surface pressure')
    axs_geom_2_twin.set_ylabel(r'Surface pressure (kPa)')
    # Add legends
    h1, l1 = axs_rate[0].get_legend_handles_labels()
    h2, l2 = axs_rate_0_twin.get_legend_handles_labels()
    axs_rate[0].legend(h1 + h2, l1 + l2, loc=3)
    h1, l1 = axs_rate[1].get_legend_handles_labels()
    h2, l2 = axs_rate_1_twin.get_legend_handles_labels()
    axs_rate[1].legend(h1 + h2, l1 + l2, loc=3)
    h1, l1 = axs_rate[2].get_legend_handles_labels()
    h2, l2 = axs_rate_2_twin.get_legend_handles_labels()
    axs_rate[2].legend(h1 + h2, l1 + l2, loc=3)
    h1, l1 = axs_geom[0].get_legend_handles_labels()
    h2, l2 = axs_geom_0_twin.get_legend_handles_labels()
    axs_geom[0].legend(h1 + h2, l1 + l2, loc=3)
    h1, l1 = axs_geom[1].get_legend_handles_labels()
    h2, l2 = axs_geom_1_twin.get_legend_handles_labels()
    axs_geom[1].legend(h1 + h2, l1 + l2, loc=3)
    h1, l1 = axs_geom[2].get_legend_handles_labels()
    h2, l2 = axs_geom_2_twin.get_legend_handles_labels()
    axs_geom[2].legend(h1 + h2, l1 + l2, loc=3)
    # Add panel labels
    for axes_id, axes in enumerate(axs_rate.ravel()):
        axes.text(-.175, 1.1, chr(65+axes_id), transform=axes.transAxes,
                  fontsize=12, fontweight='bold', va='top')
    for axes_id, axes in enumerate(axs_geom.ravel()):
        axes.text(-.2, 1.05, chr(65+axes_id), transform=axes.transAxes,
                  fontsize=12, fontweight='bold', va='top')
    # Save figure
    fig_rate.tight_layout()
    fig_geom.tight_layout()
    fname_rate = './plots/RepSample/shape_rate'
    fname_geom = './plots/RepSample/shape_geom'
    if not with_color:
        fname_rate += '_bw'
        fname_geom += '_bw'
    fig_rate.savefig(fname_rate + '.png', dpi=300)
    fig_rate.savefig(fname_rate + '.pdf', dpi=300)
    fig_geom.savefig(fname_geom + '.png', dpi=300)
    fig_geom.savefig(fname_geom + '.pdf', dpi=300)
    plt.close(fig_rate)
    plt.close(fig_geom)


def quantify_shape(repSample_list):

    def get_corr(repSample, domain, stim, quantity):
        if domain == 'rate':
            surface = 'displ' if repSample.control == 'Displ' else 'press'
            time_arr = np.linspace(0, MAX_RATE_TIME, 100)
            stimulus = np.interp(time_arr,
                                 repSample.traces_rate[stim]['time'],
                                 repSample.traces_rate[stim][surface])
            response = np.interp(time_arr,
                                 repSample.traces_rate[stim]['time'],
                                 repSample.traces_rate[stim][quantity])
        if domain == 'geom':
            surface = 'cy' if repSample.control == 'Displ' else 'cpress'
            dist = repSample.dist[stim]
            xcoord = np.linspace(0, MAX_RADIUS, 100)
            stimulus = np.interp(xcoord, dist['cxold'][-1], dist[surface][-1])
            response = np.interp(xcoord, dist['mxold'][-1],
                                 get_dist_static_mean(dist, 'm%s' % quantity))
        return pearsonr(stimulus, response)[0]

    stim = representative_stim_num
    r2_dict = dict(rate=[], geom=[])
    for control, quantity in transform_list:
        repSample = repSample_list[0][control]
        for key, item in r2_dict.items():
            item.append(get_corr(repSample, key, stim, quantity) ** 2)
    return r2_dict


def quantify_neural(repSample_list, full):
    fiber_id = FIBER_MECH_ID

    def get_range(stim, quantity, control):
        repSample_control_list = [
            repSample_list[level][control] for level in range(level_num)]
        response_arr = np.array(
            [repSample.predicted_fr[fiber_id][quantity].T[1][stim]
             for repSample in repSample_control_list])
        return response_arr.max() - response_arr.min()
    range_avg_dict = {'0_abs': [], '0_rel': [],
                      '1_abs': [], '1_rel': []}
    # This is a hack to use `iter()`, because if I try to still use
    # `transform_list` it will become a local variable, and may be referenced
    # before definition when `full == False`
    if full:
        transform_iter = iter(transform_list_full)
    else:
        transform_iter = iter(transform_list)
    for control, quantity in transform_iter:
        range_list = []
        for stim in stim_neural_quant_iter:
            range_list.append(get_range(stim, quantity, control))
        range_avg_abs = np.mean(range_list)
        range_avg_rel = range_avg_abs / repSample_list[0][
            control].predicted_fr[fiber_id][quantity].T[1][
                representative_stim_num]
        range_avg_dict['%d_abs' % control].append(range_avg_abs)
        range_avg_dict['%d_rel' % control].append(range_avg_rel)
    return range_avg_dict


def quantify_neural_mechanics(repSample_list):

    def get_range(stim, control):
        repSample_control_list = [
            repSample_list[level][control] for level in range(level_num)]
        response_arr = np.array(
            [repSample.static_force_exp[stim]
             for repSample in repSample_control_list])
        return response_arr.max() - response_arr.min()
    range_list = []
    for stim in stim_neural_quant_iter:
        range_list.append(get_range(stim, 0))
    range_avg_abs = np.mean(range_list)
    range_avg_rel = range_avg_abs / repSample_list[0][0].static_force_exp[
        representative_stim_num]
    return range_avg_abs, range_avg_rel


def plot_neural_mechanics(repSample_list, with_color=True):
    fig, axs = plt.subplots()
    x_array_list, y_array_list = [], []
    for level in level_plot_iter:
        x_array_list.append(repSample_list[level][0].static_displ_exp)
        y_array_list.append(repSample_list[level][0].static_force_exp)
    fill_between_curves(x_array_list, y_array_list, axs,
                        alpha=.25, fc='k', ec='none')
    repSample = repSample_list[0][0]
    axs.plot(
        repSample.static_displ_exp,
        repSample.static_force_exp,
        '-k', label='Average skin')
    # Plot lines for connecting traces figure
    for stim in stim_plot_list:
        color = get_color(stim) if with_color else 'k'
        x = repSample_list[0][0].static_displ_exp[stim]
        y = repSample_list[0][0].static_force_exp[stim]
        y_all = [
            repSample_list[i][0].static_force_exp[stim]
            for i in level_plot_iter]
        y_err = np.array(
            [y_all[0] - np.min(y_all), np.max(y_all) - y_all[0]])
        y_err = y_err[:, np.newaxis]
        axs.errorbar(x, y, y_err,
                     alpha=.25, c=color, capsize=0, elinewidth=4)
        annotate_text = '%.1f - %.1f mN' % (np.min(y_all), np.max(y_all))
        axs.annotate(annotate_text, xy=(x, np.max(y_all)),
                     xytext=(x, np.max(y_all) + .2),
                     color=color, ha='right')
    # X and Y limits
    axs.set_xlim(.3, .8)
    # Axes and panel labels
    axs.set_xlabel(r'Steady-state tip displacement (mm)')
    axs.set_ylabel('Steady-state tip force (mN)')
    # Legend
    axs.legend(loc=2)
    axs.set_title('Controlled tip displacement')
    # Save
    fig.tight_layout()
    if with_color:
        fig.savefig('./plots/RepSample/neural_mechanics.png', dpi=300)
        fig.savefig('./plots/RepSample/neural_mechanics.pdf', dpi=300)
    else:
        fig.savefig('./plots/RepSample/neural_mechanics_bw.png', dpi=300)
        fig.savefig('./plots/RepSample/neural_mechanics_bw.pdf', dpi=300)
    plt.close(fig)


def plot_neural(repSample_list, force_control, with_color=True):
    control = int(force_control)
    fiber_id = FIBER_MECH_ID
    fig, axs = plt.subplots(3, 2, figsize=(5, 6))
    kwargs = dict(fc='k', ec='none', alpha=.25)
    for k, quantity in enumerate(quantity_plot_list):
        x_displ_array_list, x_force_array_list = [], []
        y_displ_array_list, y_force_array_list = [], []
        for level in level_plot_iter:
            x_displ_array_list.append(
                repSample_list[level][0].static_displ_exp)
            y_displ_array_list.append(
                repSample_list[level][0].predicted_fr[
                    fiber_id][quantity].T[1])
            x_force_array_list.append(
                repSample_list[level][control].static_force_exp)
            y_force_array_list.append(
                repSample_list[level][control].predicted_fr[
                    fiber_id][quantity].T[1])
        fill_between_curves(
            x_displ_array_list, y_displ_array_list,
            axs[k, 0], **kwargs)
        fill_between_curves(
            x_force_array_list, y_force_array_list,
            axs[k, 1], **kwargs)
        # Plot median
        simFiber = repSample_list[0][0]
        axs[k, 0].plot(
            simFiber.static_displ_exp,
            simFiber.predicted_fr[fiber_id][quantity].T[1],
            '-k', label='Average skin mechanics')
        simFiber = repSample_list[0][control]
        axs[k, 1].plot(
            simFiber.static_force_exp,
            simFiber.predicted_fr[fiber_id][quantity].T[1],
            '-k', label='Average skin mechanics')
    # Plot lines for connecting traces figure

    def add_colored_bands(axes, quantity, control):
        for stim in stim_plot_list:
            color = get_color(stim) if with_color else 'k'
            if control == 0:
                x = repSample_list[0][control].static_displ_exp[stim]
            elif control == 1:
                x = repSample_list[0][control].static_force_exp[stim]
            y = repSample_list[0][control].predicted_fr[fiber_id][
                quantity].T[1][stim]
            y_all = [
                repSample_list[i][control].predicted_fr[fiber_id][
                    quantity].T[1][stim]
                for i in level_plot_iter]
            y_err = np.array(
                [y_all[0] - np.min(y_all), np.max(y_all) - y_all[0]])
            y_err = y_err[:, np.newaxis]
            axes.errorbar(x, y, y_err,
                          alpha=.25, c=color, capsize=0, elinewidth=4)
            annotate_text = '%d - %d Hz' % (np.min(y_all), np.max(y_all))
            axes.annotate(annotate_text, xy=(x, np.max(y_all)),
                          xytext=(x, np.max(y_all) + 2),
                          color=color, ha='right')
    add_colored_bands(axs[0, 0], 'strain', 0)
    add_colored_bands(axs[1, 0], 'sener', 0)
    if force_control:
        add_colored_bands(axs[2, 1], 'stress', 1)
    # X and Y limits
    for axes in axs.ravel():
        axes.set_ylim(0, 50)
    for axes in axs[0].ravel():
        axes.set_ylim(0, 80)
    for axes in axs[:, 0]:
        axes.set_xlim(.3, .8)
    for axes in axs[:, 1]:
        axes.set_xlim(0, 8)
    # Axes and panel labels
    for axes in axs[:, 0]:
        axes.set_xlabel(r'Steady-state tip displacement (mm)')
    for axes in axs[:, 1]:
        axes.set_xlabel(r'Steady-state tip force (mN)')
    for i, axes in enumerate(axs[:, 0].ravel()):
        axes.set_ylabel('Static firing (Hz) \nPredicted from interior %s' %
                        (['strain', 'SED', 'stress'][i]))
    for axes_id, axes in enumerate(axs.ravel()):
        if axes_id % 2:
            x = -.15
        else:
            x = -.2
        axes.text(x, 1.13, chr(65+axes_id), transform=axes.transAxes,
                  fontsize=12, fontweight='bold', va='top')
    axs[0, 0].set_title('Controlled tip displacement')
    axs[0, 1].set_title('Controlled tip force')
    # Legends
    handels, labels = axs[0, 1].get_legend_handles_labels()
    axs[0, 1].legend(handels[0:1], ['Average skin'], loc=2)
    # Save
    fig.tight_layout()
    if with_color:
        fig.savefig('./plots/RepSample/neural.png', dpi=300)
        fig.savefig('./plots/RepSample/neural.pdf', dpi=300)
    else:
        fig.savefig('./plots/RepSample/neural_bw.png', dpi=300)
        fig.savefig('./plots/RepSample/neural_bw.pdf', dpi=300)
    plt.close(fig)


def plot_neural_geom(repSample_list):
    fiber_id = FIBER_MECH_ID
    fig, axs = plt.subplots(3, 2, figsize=(5, 6))
    kwargs = dict(fc='k', ec='none', alpha=.25)
    stim = representative_stim_num
    for row, quantity in enumerate(quantity_plot_list):
        x_displ_array_list, x_force_array_list = [], []
        y_displ_array_list, y_force_array_list = [], []
        for level in level_plot_iter:
            dist_displ = repSample_list[level][0].dist[stim]
            dist_force = repSample_list[level][1].dist[stim]
            dist_fr_displ = repSample_list[level][0].dist_fr[
                fiber_id][quantity][stim, 0, :]
            dist_fr_force = repSample_list[level][1].dist_fr[
                fiber_id][quantity][stim, 0, :]
            x_displ_array_list.append(dist_displ['mxold'][-1, :] * 1e3)
            x_force_array_list.append(dist_force['mxold'][-1, :] * 1e3)
            y_displ_array_list.append(dist_fr_displ)
            y_force_array_list.append(dist_fr_force)
        fill_between_geom_curves(
            x_displ_array_list, y_displ_array_list,
            axs[row, 0], **kwargs)
        fill_between_geom_curves(
            x_force_array_list, y_force_array_list,
            axs[row, 1], **kwargs)
        # Plot median
        axs[row, 0].plot(
            x_displ_array_list[0], y_displ_array_list[0],
            '-k', label='Average skin mechanics')
        axs[row, 1].plot(
            x_force_array_list[0], y_force_array_list[0],
            '-k', label='Average skin mechanics')
    # X and Y limits
    for axes in axs.ravel():
        axes.set_xlim(right=MAX_RADIUS * 1e3)
        axes.set_ylim(top=100)
    # Axes and panel labels
    for axes in axs.ravel():
        axes.set_xlabel(r'Location (mm)')
    for i, axes in enumerate(axs[:, 0].ravel()):
        axes.set_ylabel('Static firing (Hz) \nPredicted from interior %s' %
                        (['strain', 'SED', 'stress'][i]))
    for axes_id, axes in enumerate(axs.ravel()):
        if axes_id % 2:
            x = -.15
        else:
            x = -.2
        axes.text(x, 1.15, chr(65+axes_id), transform=axes.transAxes,
                  fontsize=12, fontweight='bold', va='top')
    axs[0, 0].set_title('Controlled tip displacement')
    axs[0, 1].set_title('Controlled tip force')
    # Legends
    handels, labels = axs[0, 0].get_legend_handles_labels()
    axs[0, 0].legend(handels[0:1], ['Average skin'], loc=2)
    # Save
    fig.tight_layout()
    fig.savefig('./plots/RepSample/neural_geom.png', dpi=300)
    fig.savefig('./plots/RepSample/neural_geom.pdf', dpi=300)
    plt.close(fig)


def quantify_std(repSample_list, stim=4):
    fr_list = []
    fiber_id = FIBER_MECH_ID
    for i in range(6):
        repSample = repSample_list[i][0]
        fr_list.append(repSample.predicted_fr[fiber_id]['strain'].T[1][stim])
    return np.std(fr_list, ddof=1)


if __name__ == '__main__':
    run_fiber = False
    fname = './pickles/repSample_list.pkl'
    if run_fiber:
        # Generate data
        repSample_list = [[] for j in range(level_num)]
        for level in range(level_num):
            j = level
            for k, control in enumerate(control_list):
                repSample = RepSample(level, control, stim_num)
                repSample_list[j].append(repSample)
                print('RepSample%d%s done ...' % (j, control))
        # Store data
        with open(fname, 'wb') as f:
            pickle.dump(repSample_list, f)
    else:
        with open(fname, 'rb') as f:
            repSample_list = pickle.load(f)
    # %% Ploting
    plot_variance(repSample_list)
    plot_shape(repSample_list)
    plot_shape(repSample_list, with_color=False)
    plot_neural_mechanics(repSample_list)
    plot_neural_mechanics(repSample_list, with_color=False)
    plot_neural(repSample_list, force_control=True)
    plot_neural(repSample_list, force_control=True, with_color=False)
    plot_neural_geom(repSample_list)
    # %% Make quantification table
    # Obtain values
    isrd_list = quantify_variance(repSample_list)
    r2_dict = quantify_shape(repSample_list)
    # Make dataframe
    table_dict = r2_dict.copy()
    table_dict.update({'isrd': isrd_list})
    table_df = pd.DataFrame(table_dict)
    # Reorder columns and add indices
    columns = ['isrd', 'rate', 'geom']
    table_df = table_df[columns]
    table_df.columns = ['Magnitude conveyance',
                        'Rate preservation', 'Geometry preservation']
    table_df.index = ['Deflection-to-strain', 'Deflection-to-SED',
                      'Pressure-to-stress']
    table_df.to_csv('./csvs/RepSample/table_df.csv')
    # Data for writing but not in table
    range_mechanics_abs, range_mechanics_rel = quantify_neural_mechanics(
        repSample_list)
    stim_neural_quant_displ_list = [repSample_list[0][0].static_displ_exp[i]
                                    for i in stim_neural_quant_iter]
    stim_neural_quant_force_list = [repSample_list[0][1].static_force_exp[i]
                                    for i in stim_neural_quant_iter]
    representative_stim_num_displ = repSample_list[0][0].static_displ_exp[
        representative_stim_num]
    representative_stim_num_force = repSample_list[0][1].static_force_exp[
        representative_stim_num]
    # Order of skin mechanics from min to max for displ
    fr_list_for_each_skin = [
        repSample_list[i][0].predicted_fr[FIBER_MECH_ID]['stress'][-1, 1]
        for i in range(level_num)]
    print('Skin order for displ. case: ',
          np.argsort(fr_list_for_each_skin) + 1)
    # List of stimuli
    repSample = repSample_list[0][0]
    np.savetxt('./csvs/RepSample/stim_displ.csv',
               repSample.static_displ_exp[None],
               delimiter=', ', fmt='%.2f')
    repSampleForce = repSample_list[0][1]
    np.savetxt('./csvs/RepSample/stim_force.csv',
               repSampleForce.static_force_exp[None],
               delimiter=', ', fmt='%.2f')
    # %% Make the new table - with full neural quantification
    range_avg_dict = quantify_neural(repSample_list, full=True)
    range_avg_df = pd.DataFrame(range_avg_dict,
                                index=['Strain', 'SED', 'Stress'])
    range_avg_df.to_csv('./csvs/RepSample/neural_table.csv')
