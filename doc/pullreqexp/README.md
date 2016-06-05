Pull Requests of Experiments
============================

Some contributors may experiment new features and send pull requests to Docklet official repository. Sometimes the requests will be refused for reasons like functional incompatibility, deviation of development plan, lacking of fully testing, etc. However, some experiments may be very interesting and helpful. Therefore we recommend contributors write down the goal, design, and evaluation of their experiments in markdown format, and send pull requests here about the markdown file.

## Guide 

1. Experiment on the forked unias/docklet repository and make sure it work as expected
2. Switch to **experiment** branch, write down a markdown doc named to document the experiment
3. Send a pull request to unias/docklet **experiment** branch

## Doc template

```
# Title of the Experiments

Author: [Author name](Author email)
Source Code: https://github.com/yourname/docklet/

## Goal

## Design

## Experiments

## Summary

```

It is recommended to write markdown that could be interepreted by
remark, please refer the **demo** dir.
